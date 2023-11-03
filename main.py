from flask import Flask, render_template, Markup, request
import json
import requests
import pandas as pd
import io
import re

app = Flask(__name__)


@app.route('/')
def index():
    
    uri = request.args.get("uri", "https://ld.admin.ch/country/CHE")
    env = request.args.get("env", "prod")
    dir = request.args.get("dir", "nominal")
    
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
        "Accept": "application/json" 
    }

    response = requests.post(sparql_endpoint_url, 
                             data=encoded_query, 
                             headers=headers)
    
    response.encoding = "utf-8"

    if response.status_code == 200:
        
        data = response.json()

        vars = data["head"]["vars"]

        df = pd.DataFrame(columns = vars)

        for line in data["results"]["bindings"]:
            line_list = []
            for col in line:
                if col["type"] == "uri":
                    url = modify_uri(col["value"], env, dir)
                    line_list.append(url)
                
                elif col["type"] == "literal":
                    line_list.append(col["value"])

                else:
                    line_list.append(col["value"])

            row_to_append = pd.DataFrame([line_list], columns = vars)

            df = df.append(row_to_append, ignore_index=True)

        df = df.map(lambda x: Markup(x))

        return render_template('dataframe.html', data=df, uri=uri, env=env, dir=dir, col_names=vars)

    else:
        print(f"SPARQL query failed with status code: {response.status_code} and response text: {response.text}!")
        return render_template('template.html', uri=uri)

    

def linker(input_string, env, dir):

    # geo.ld.admin.ch and schema.ld.admin.ch are nor regularly dereferenced
    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"
    
    # all URI starting with something.ld.admin.ch or ld.admin.ch should be dereference within flader
    pattern = r'^https://[^/]+\.ld\.admin\.ch'
    
    if input_string.startswith("https://ld.admin.ch") or re.match(pattern, input_string):
        return "<a href='https://flader.di.digisus-lab.ch?uri=" + input_string + "&env=" + env + "&dir=" + dir + "'>" + input_string + "</a>"
    
    # external URI
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"

    # if string literal
    return input_string


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)