from flask import Flask, render_template, Markup, request
import os
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

        print("\n reverse \n")

        sparql_query = """

        SELECT * WHERE {
            ?subject ?predicate <""" + uri + """>.
        }

        """

    else:
        dir = "nominal"

        sparql_query = """

        SELECT * WHERE {
            <""" + uri + """> ?predicate ?object.
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
        "Accept": "text/csv" 
    }

    response = requests.post(sparql_endpoint_url, 
                             data=encoded_query, 
                             headers=headers)
    
    response.encoding = "utf-8"

    if response.status_code == 200:
        df = pd.read_csv(io.StringIO(response.text))
        
        # replace NA values by empty strings
        df.fillna("", inplace = True) 

        df = df.map(lambda x: linker(x, env))
        df = df.map(lambda x: Markup(x))

        col_names = df.columns.tolist()

        return render_template('dataframe.html', data=df, subject=uri, env=env, col_names=col_names)

    else:
        print(f"SPARQL query failed with status code: {response.status_code} and response text: {response.text}!")
        return render_template('template.html', uri=uri)

    

def linker(input_string, env):

    # geo.ld.admin.ch and schema.ld.admin.ch are nor regularly dereferenced
    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"
    
    # all URI starting with something.ld.admin.ch or ld.admin.ch should be dereference within flader
    pattern = r'^https://[^/]+\.ld\.admin\.ch'
    
    if input_string.startswith("https://ld.admin.ch") or re.match(pattern, input_string):
        return "<a href='https://flader.di.digisus-lab.ch?uri=" + input_string + "&env=" + env + "'>" + input_string + "</a>"
    
    # external URI
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"

    # if string literal
    return input_string


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)