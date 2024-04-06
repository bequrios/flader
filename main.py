from flask import Flask, render_template, Markup, request
import json
import requests
import pandas as pd
import io
import re

app = Flask(__name__)


@app.route('/')
def index():
    
    # url parameter and their default values
    uri = request.args.get("uri", "https://ld.admin.ch/country/CHE")
    env = request.args.get("env", "prod")
    ext = request.args.get("ext", "false")
    dir = request.args.get("dir", "nominal")
    limit = request.args.get("limit", "0")
    
    if dir == "reverse":

        sparql_query = """

        SELECT ?subject ?predicate ?graph WHERE {
            GRAPH ?graph {
                ?subject ?predicate <""" + uri + """>.
            }
        }

        """

    else:
        dir = "nominal"

        sparql_query = """

        SELECT ?predicate ?object ?graph WHERE {
            GRAPH ?graph {
                <""" + uri + """> ?predicate ?object.
            }
        }

        """

    if limit != "0":
        sparql_query = sparql_query + "LIMIT " + limit

    encoded_query = {"query": sparql_query}

    if env == "test":
        lindas_enpoint_url = "https://test.ld.admin.ch/query"
    elif env == "int":
        lindas_enpoint_url = "https://int.ld.admin.ch/query"
    else:
        env = "prod"
        lindas_enpoint_url = "https://ld.admin.ch/query"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "application/sparql-results+json" 
    }

    status = "nok"

    response_lindas = requests.post(lindas_enpoint_url, 
                             data=encoded_query, 
                             headers=headers)
    

    if response_lindas.status_code == 200:

        response_lindas.encoding = "utf-8"

        data_lindas = response_lindas.json()

        # the variables of the query result
        vars = data_lindas["head"]["vars"]

        df = pd.DataFrame(columns = vars)

        data = data_lindas["results"]["bindings"]

        status = "ok"

    if ext == "true":

        response_ext = requests.post("http://graphdb.di.digisus-lab.ch/repositories/flader",
                             data=encoded_query,
                             headers=headers)
        
        if response_ext.status_code == 200:

            response_ext.encoding = "utf-8"

            data_ext = response_ext.json()

            data = data + data_ext["results"]["bindings"]

            status = "ok"

        else:
            status = "nok"

    if status == "ok":
        
        # for each line in the result table
        for line in data:
            line_list = []
            
            # for every column (variable)
            for var in vars:
                
                # if uri or blank node
                if line[var]["type"] == "uri" or line[var]["type"] == "bnode":
                    url = modify_uri(line[var]["value"], env, ext, dir, limit)
                    line_list.append(url)
                
                # if string literal
                elif line[var]["type"] == "literal":
                    
                    # if language tag present
                    if "xml:lang" in line[var]:
                        line_list.append(line[var]["value"] + ' <span class="text-muted">@' + line[var]["xml:lang"] + "</span>")
                    
                    # if datatype present
                    elif "datatype" in line[var]:
                        #match = re.search(r'#(.*)', line[var]["datatype"])
                        #datatype = "xsd:" + match.group(1)
                        line_list.append(line[var]["value"] + " <span class='text-muted'>" + prefixer(line[var]["datatype"]) + "</span>")
                    else: #könnte trotzdem ein URL sein, der aber vom Server als Literal geschickt wird
                        #line_list.append(line[var]["value"])
                        url = modify_uri(line[var]["value"], env, ext, dir, limit)
                        line_list.append(url)

                else:
                    line_list.append(line[var]["value"])

            row_to_append = pd.DataFrame([line_list], columns = vars)

            df = pd.concat([df, row_to_append], ignore_index=True)

        # define all cells as markup so that the html code is properly displayed
        df = df.map(lambda x: Markup(x))

        return render_template('dataframe.html', data=df, uri=uri, env=env, ext=ext, dir=dir, limit=limit, col_names=vars)

    else:
        print(f"status code lindas: {response_lindas.status_code} and response text lindas: {response_lindas.text}, status code ext: {response_ext.status_code} and response text ext: {resonse_ext.text}!")
        return render_template('template.html', uri=uri)

# modifies the uris for correct linking (uri will be resolved with flader as long as possible)
def modify_uri(input_string, env, ext, dir, limit):

    # geo.ld.admin.ch and schema.ld.admin.ch are not regularly dereferenced
    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"
    
    # all URI starting with something.ld.admin.ch or ld.admin.ch or example.com should be dereferenced within flader
    pattern = r'^https://[^/]+\.ld\.admin\.ch'
    
    if input_string.startswith("https://ld.admin.ch") or re.match(pattern, input_string) or input_string.startswith("https://example.com"):
        return "<a href='https://flader.di.digisus-lab.ch?uri=" + input_string + "&env=" + env + "&ext=" + ext + "&dir=" + dir + "&limit=" + limit + "'>" + prefixer(input_string) + "</a>"
    
    # external URI
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + prefixer(input_string) + "</a>"
    
    # blank node
    if input_string.startswith("genid"):
        return "<a href='https://flader.di.digisus-lab.ch?uri=_:" + input_string + "&env=" + env + "&ext=" + ext + "&dir=" + dir + "&limit=" + limit + "'>" + input_string + "</a>"

    # if string literal
    return input_string

def prefixer(text):

    prefixes = {
        "http://schema.org/": "schema:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "http://www.w3.org/ns/prov#": "prov:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://purl.org/dc/terms/": "dcterms:",
        "https://version.link/": "vl:",
        "https://cube.link/": "cube:",
        "http://www.w3.org/2002/07/owl#": "owl:",
        "http://www.w3.org/ns/dcat#": "dcat:",
        "http://rdfs.org/ns/void#": "void:",
        "https://lindas.admin.ch/": "lindas:",
        "http://www.w3.org/2001/XMLSchema#": "xsd:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "https://example.com/": ":"
    }

    # Replace all occurrences of the keys with their corresponding values
    for key, value in prefixes.items():
        text = text.replace(key, value)
    
    return text

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)