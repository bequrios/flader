from flask import Flask, render_template, Markup, request
import requests
import pandas as pd
import re

app = Flask(__name__)

@app.route('/')
def index():
    
    # url parameter and their default values
    uri = request.args.get("uri", "https://ld.admin.ch/country/CHE")
    env = request.args.get("env", "prod")
    ext = request.args.get("ext", "false")
    dir = request.args.get("dir", "nominal")
    lim = request.args.get("lim", "0")
    
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

    if lim != "0":
        sparql_query = sparql_query + "LIMIT " + lim

    encoded_query = {"query": sparql_query}

    if env == "test":
        lindas_enpoint_url = "https://test.ld.admin.ch/query"
    elif env == "int":
        lindas_enpoint_url = "https://int.ld.admin.ch/query"
    elif env == "prod":
        lindas_enpoint_url = "https://ld.admin.ch/query"
    else:
        env == "off"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Accept": "application/sparql-results+json" 
    }

    status_lindas = "ok"
    status_ext = "ok"

    # empty result dictionary
    data = []

    # empty variable list
    vars = []

    # if LINDAS is not set to "off"
    if env != "off":
        response_lindas = requests.post(lindas_enpoint_url, 
                             data=encoded_query, 
                             headers=headers)
    
        if response_lindas.status_code == 200:
            response_lindas.encoding = "utf-8"
            data_lindas = response_lindas.json()
            # the variables of the query result
            vars = data_lindas["head"]["vars"]
            data = data + data_lindas["results"]["bindings"]
        else:
            status_lindas = "nok"

    if ext == "true":
        response_ext = requests.post("http://graphdb.di.digisus-lab.ch/repositories/flader",
                             data=encoded_query,
                             headers=headers)
        
        if response_ext.status_code == 200:
            response_ext.encoding = "utf-8"
            data_ext = response_ext.json()
            vars = data_ext["head"]["vars"]
            data = data + data_ext["results"]["bindings"]
        else:
            status_ext = "nok"

    if (status_lindas == "ok" and status_ext == "ok"):
        
        lines = []
        
        # for each line in the result table
        for line in data:
            line_list = []
            
            # for every column (variable)
            for var in vars:
                # if uri or blank node
                if line[var]["type"] == "uri" or line[var]["type"] == "bnode":
                    url = modify_uri(line[var]["value"], env, ext, dir, lim)
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
                        url = modify_uri(line[var]["value"], env, ext, dir, lim)
                        line_list.append(url)

                else:
                    line_list.append(line[var]["value"])

            lines.append(line_list)

        df = pd.DataFrame(lines, columns = vars)

        # define all cells as markup so that the html code is properly displayed
        df = df.map(lambda x: Markup(x))

        return render_template('dataframe.html', data=df, uri=uri, env=env, ext=ext, dir=dir, lim=lim, col_names=vars)

    else:
        error_message = ""

        if status_lindas == "nok":
            error_message += f"status code lindas: {response_lindas.status_code} and response text lindas: {response_lindas.text}! "

        if status_ext == "nok":
            error_message += f"status code ext: {response_ext.status_code} and response text ext: {response_ext.text}!"
    
        return render_template('error.html', error=error_message)


@app.route('/cyto')
def cyto():

    def path(query_string, address):

        # Define the headers for the request
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        
        # URL-encode the query parameters
        payload = {'query': query_string}
        
        # Send the request to the SPARQL endpoint
        response = requests.post(address, data=payload, headers=headers)

        # Ensure the response uses UTF-8 encoding
        response.encoding = 'utf-8'
        
        # Raise an exception if the request was not successful
        response.raise_for_status()

        # Parse the JSON response
        results = response.json()

        return results
    
    def color_map(code):
        if code == "29-26":
            return "blue"
        elif code == "26-26":
            return "green"
        elif code == "29-21" or code == "26-21":
            return "orange"
        else:
            return "grey"
        
    res = path("""

    PREFIX schema: <http://schema.org/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX ech: <https://ld.admin.ch/ech/71/>

    PATHS 
    START ?x = <https://ld.admin.ch/municipality/version/14062> #Berg (TG)
    #START ?x = <https://ld.admin.ch/municipality/version/13445> #Rubigen
    #START ?x = <https://ld.admin.ch/municipality/version/14091> #Eschlikon
    #START ?x = <https://ld.admin.ch/municipality/version/12612> #Lavertezzo
    END ?y 

    VIA {

        ?x ?p ?y.
        
        ?x schema:name ?xName;
            prov:hadPrimarySource ?xECH;
            schema:validFrom ?xAdDate.
        ?y schema:name ?yName;
            prov:hadPrimarySource ?yECH;
            schema:validFrom ?yAdDate.
            
        OPTIONAL {?x schema:validThrough ?xAbDate.}
        OPTIONAL {?y schema:validThrough ?yAbDate.}
            
        OPTIONAL {?xECH ech:municipalityAbolitionModeId ?xECHAbId.}
        OPTIONAL {?xECH ech:municipalityAdmissionModeId ?xECHAdId.}
            
        OPTIONAL {?yECH ech:municipalityAbolitionModeId ?yECHAbId.}
        OPTIONAL {?yECH ech:municipalityAdmissionModeId ?yECHAdId.}
        
        FILTER(?p = <https://version.link/successor> || ?p = <https://version.link/predecessor>)

    }

    """, "https://ld.admin.ch/query")

    results = []

    for entry in res["results"]["bindings"]:
        if "x" in entry:
            if entry["p"]["value"] == "https://version.link/successor":
                results.append(
                    {
                        "source": entry["x"]["value"], 
                        "sourceName": entry["xName"]["value"],
                        "abolitionDate": entry["xAbDate"]["value"],
                        "abolitionId": entry["xECHAbId"]["value"],
                        "admissionId": entry["yECHAdId"]["value"],
                        "admissionDate": entry["yAdDate"]["value"],
                        "targetName": entry["yName"]["value"],
                        "target": entry["y"]["value"]
                    }
                )
            else:
                results.append(
                    {
                        "source": entry["y"]["value"], 
                        "sourceName": entry["yName"]["value"],
                        "abolitionDate": entry["yAbDate"]["value"],
                        "abolitionId": entry["yECHAbId"]["value"],
                        "admissionId": entry["xECHAdId"]["value"],
                        "admissionDate": entry["xAdDate"]["value"],
                        "targetName": entry["xName"]["value"],
                        "target": entry["x"]["value"]
                    }
                )
                
    df = pd.DataFrame(results).drop_duplicates()

    df["abolitionDate"] = pd.to_datetime(df["abolitionDate"])
    df["admissionDate"] = pd.to_datetime(df["admissionDate"])
    df["changeMode"] = df["abolitionId"] + "-" + df["admissionId"] #Kombination aus AbolitionMode und AdmissionMode
    df["color"] = df["changeMode"].map(color_map) #erstellen einer neuen Spalte für die Farben der Pfeile beruhend auf dem changeMode
                
    df.sort_values("admissionDate", inplace=True)

    # Build unique nodes set
    nodes = {}
    for _, row in df.iterrows():
        nodes[row['source']] = {"id": row['source'], "label": row['sourceName']}
        nodes[row['target']] = {"id": row['target'], "label": row['targetName']}

    # Build edges
    edges = []
    for _, row in df.iterrows():
        edges.append({
            "data": {
                "source": row["source"],
                "target": row["target"],
                "color": row["color"]
            }
        })

    # Format as graph_data JSON
    graph_data = {
        "nodes": [{"data": node} for node in nodes.values()],
        "edges": edges
    }
    
    # Pass the data to the template
    return render_template('cyto.html', graph_data=graph_data)


# modifies the uris for correct linking (uri will be resolved with flader as long as possible)
def modify_uri(input_string, env, ext, dir, lim):

    # geo.ld.admin.ch and schema.ld.admin.ch are not regularly dereferenced
    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"
    
    # all URI starting with something.ld.admin.ch or ld.admin.ch or example.com should be dereferenced within flader
    pattern = r'^https://[^/]+\.ld\.admin\.ch'
    
    if input_string.startswith("https://ld.admin.ch") or re.match(pattern, input_string) or input_string.startswith("https://example.com"):
        return "<a href='https://flader.di.digisus-lab.ch?uri=" + input_string + "&env=" + env + "&ext=" + ext + "&dir=" + dir + "&lim=" + lim + "'>" + prefixer(input_string) + "</a>"
    
    # external URI
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + prefixer(input_string) + "</a>"
    
    # blank node
    if input_string.startswith("genid") or input_string.startswith("anon-genid"):
        return "<a href='https://flader.di.digisus-lab.ch?uri=_:" + input_string + "&env=" + env + "&ext=" + ext + "&dir=" + dir + "&lim=" + lim + "'>" + input_string + "</a>"

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
        "https://example.com/": ":",
        "https://flader.di.digisus-lab.ch/": "flader:"
    }

    # Replace all occurrences of the keys with their corresponding values
    for key, value in prefixes.items():
        text = text.replace(key, value)
    
    return text

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)