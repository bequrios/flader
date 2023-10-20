from flask import Flask, render_template, Markup, request
import os
import requests
import pandas as pd
import io
import re

app = Flask(__name__)


@app.route('/<path:custom_path>')
def arbitrary_path_route(custom_path):
    
    env = request.args.get("env", "prod")
    dir = request.args.get("dir", "nominal")
    
    if dir == "reverse":

        print("\n reverse \n")

        sparql_query = """

        SELECT * WHERE {
            ?subject ?predicate <https://""" + custom_path + """>.
        }

        """

    else:
        dir = "nominal"

        sparql_query = """

        SELECT * WHERE {
            <https://""" + custom_path + """> ?predicate ?object.
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

        return render_template('dataframe.html', data=df, subject=custom_path, env=env, col_names=col_names)

    else:
        print(f"SPARQL query failed with status code: {response.status_code} and response text: {response.text}!")
        return render_template('template.html', custom_path=custom_path)

    

def linker(input_string, env):

    if input_string.startswith("https://geo.ld.admin.ch") or input_string.startswith("https://schema.ld.admin.ch"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"

    # Define the pattern you want to match
    pattern = r"https://(.*?\.ld\.admin\.ch)"

    # Define the replacement string
    replacement = r"https://flader.di.digisus-lab.ch/\1"

    # Use re.sub to perform the replacement
    result = re.sub(pattern, replacement, input_string)

    if result != input_string:
        return "<a href='" + result + "?env=" + env + "'>" + input_string + "</a>"
    
    # Define the pattern to search for
    pattern = r'(https://)(ld\.admin\.ch/.*)'

    # Define the replacement string
    replacement = r'\1flader.di.digisus-lab.ch/\2'

    # Use re.sub to replace the matched pattern with the replacement
    result = re.sub(pattern, replacement, input_string)

    if result != input_string:
        return "<a href='" + result + "?env=" + env + "'>" + input_string + "</a>"
    
    if input_string.startswith("http://") or input_string.startswith("https://"):
        return "<a href='" + input_string + "'>" + input_string + "</a>"

    return input_string


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8081)