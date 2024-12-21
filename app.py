import sqlite3
from flask import Flask
import json
from student import Student
import pyodbc
import pandas as pd
import numpy as np
import sklearn as sk
from sklearn.metrics.pairwise import cosine_similarity
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

connection = pyodbc.connect(
    'Driver={SQL Server};'
    'Server=DESKTOP-AS6A4E3;'
    'Database=EshopApiDb;'
    'Trusted_Connection=yes;'
)


@app.route('/getCustomers', methods=['GET'])
def get_students():
    query = "SELECT * FROM Customer"
    df = pd.read_sql_query(query, connection)
    print('Retrieving Customers!')
    return df

@app.route('/getSuggestions', methods=['GET'])
def get_suggestions():
    query = '''select CustomerId, ProductId, p.Name as ProductName from Customer c
            inner join [Order] o on c.Id = o.CustomerId
            inner join Item i on o.ItemId = i.Id
            inner join product p on i.ProductId = p.Id'''
    
    query_to_get_customers = "SELECT * FROM Customer"
    df = pd.read_sql_query(query, connection)

    df.drop_duplicates(inplace=True)

    df_product_names = df[['ProductId', 'ProductName']]
    df_product_names.drop_duplicates(inplace=True)

    customer_data = {}
    for _, row in df.iterrows():
        customer_id = row['CustomerId']
        product_id = row['ProductId']
        
        if customer_id not in customer_data:
            customer_data[customer_id] = []
        
        if product_id not in customer_data[customer_id]:
            customer_data[customer_id].append(product_id)
    

    user_id = 1
    users = sorted(df['CustomerId'].unique())
    recommendations = {}

    for attr in users:
        try:
            suggestionsForUser = recommend_products(customer_data, attr, num_recommendations=3)
            print(f"Recommendations for {user_id}: {recommendations}")
            recommendations[attr] = suggestionsForUser
        except Exception as e:
            recommendations[attr] = [] 

    recommendations_df = dict_to_dataframe(recommendations)

    recommendations_df = pd.merge(recommendations_df, df_product_names, on='ProductId', how='inner')

    customer_name = pd.read_sql_query(query_to_get_customers, connection)
    customer_name = customer_name.drop_duplicates()
    customer_name.rename(columns={'Id': 'CustomerId'}, inplace=True)
    customer_name['FullName'] = customer_name['FirstName'] + ' ' + customer_name['LastName']
    customer_name.drop(['FirstName', 'LastName'], axis=1, inplace=True)
    recommendations_df = pd.merge(recommendations_df, customer_name, on='CustomerId', how='inner')


    return recommendations_df.to_json(orient='records')

def dict_to_dataframe(input_dict):
    result_list = []
    for key, values in input_dict.items():
        for value in values:
            result_list.append((key, value))
    
    df = pd.DataFrame(result_list, columns=['CustomerId', 'ProductId'])
    return df

def build_user_item_matrix(data):
    products = sorted(list({product for products_list in data.values() for product in products_list}))
    users = sorted(data.keys())
    user_item_matrix = np.zeros((len(users), len(products)), dtype=int)
    
    try:
        for i, user in enumerate(users):
            for product in data[user]:
                j = products.index(product)
                user_item_matrix[i, j] = 1
    except Exception as e:
        print(e)
    
    return users, products, user_item_matrix

def get_similar_users(user_item_matrix, user_index):
    similarities = cosine_similarity([user_item_matrix[user_index]], user_item_matrix)
    similar_users_indices = np.argsort(similarities[0])[::-1][1:]  # Exclude the input user
    return similar_users_indices

def recommend_products(data, user, num_recommendations=1):

    if(len(data) == 1 or len(data) == 0 ):
        return []

    users, products, user_item_matrix = build_user_item_matrix(data)
    user_index = users.index(user)
    
    similar_users_indices = get_similar_users(user_item_matrix, user_index)
    
    recommended_products = []
    for user_idx in similar_users_indices:
        for product_idx in range(len(products)):
            if user_item_matrix[user_idx, product_idx] == 0:
                recommended_products.append(products[product_idx])
                if len(recommended_products) == num_recommendations:
                    return recommended_products
    
    return recommended_products

if __name__ == '__main__':
    app.run(port=8888)