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
        sparql_endpoint_url = "https://test.ld.admin.ch/query"
    elif env == "int":
        sparql_endpoint_url = "https://int.ld.admin.ch/query"
    else:
        env = "prod"
        sparql_endpoint_url = "https://ld.admin.ch/query"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "application/sparql-results+json" 
    }

    response = requests.post(sparql_endpoint_url, 
                             data=encoded_query, 
                             headers=headers)
    
    response.encoding = "utf-8"

    if response.status_code == 200:
        
        data = response.json()

        # the variables of the query result
        vars = data["head"]["vars"]

        df = pd.DataFrame(columns = vars)

        # for each line in the result table
        for line in data["results"]["bindings"]:
            line_list = []
            
            # for every column (variable)
            for var in vars:
                
                # if uri or blank node
                if line[var]["type"] == "uri" or line[var]["type"] == "bnode":
                    url = modify_uri(line[var]["value"], env, dir, limit)
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
                        url = modify_uri(line[var]["value"], env, dir, limit)
                        line_list.append(url)

                else:
                    line_list.append(line[var]["value"])

            row_to_append = pd.DataFrame([line_list], columns = vars)

            df = pd.concat([df, row_to_append], ignore_index=True)

        # define all cells as markup so that the html code is properly displayed
        df = df.map(lambda x: Markup(x))

        return render_template('dataframe.html', data=df, uri=uri, env=env, dir=dir, limit=limit, col_names=vars)

    else:
        print(f"SPARQL query failed with status code: {response.status_code} and response text: {response.text}!")
        return render_template('template.html', uri=uri)

# modifies the uris for correct linking (uri will be resolved with flader as long as possible)
def modify_uri(input_string, env, dir, limit):

    # geo.ld.admin.ch and schema.ld.admin.ch are nor regularly dereferenced
    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"
    
    # all URI starting with something.ld.admin.ch or ld.admin.ch should be dereference within flader
    pattern = r'^https://[^/]+\.ld\.admin\.ch'
    
    if input_string.startswith("https://ld.admin.ch") or re.match(pattern, input_string):
        return "<a href='https://flader.di.digisus-lab.ch?uri=" + input_string + "&env=" + env + "&dir=" + dir + "&limit=" + limit + "'>" + input_string + "</a>"
    
    # external URI
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + prefixer(input_string) + "</a>"
    
    # blank node
    if input_string.startswith("genid"):
        return "<a href='https://flader.di.digisus-lab.ch?uri=_:" + input_string + "&env=" + env + "&dir=" + dir + "&limit=" + limit + "'>" + input_string + "</a>"

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
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:"
    }

    # Replace all occurrences of the keys with their corresponding values
    for key, value in prefixes.items():
        text = text.replace(key, value)
    
    return text

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)