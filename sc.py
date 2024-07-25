from flask import Flask, request, jsonify
import sqlite3
import re
import requests
import os
import sys

app = Flask(__name__)

DATABASE_URI = 'spreadsheet.db'
FBASE = os.environ["FBASE"]
FIREBASE_URL = f'https://{FBASE}-default-rtdb.europe-west1.firebasedatabase.app/'
created_cells = set()

def init_db():
    with sqlite3.connect(DATABASE_URI) as connection:
        cursor = connection.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS cells
                          (id TEXT PRIMARY KEY, formula TEXT)''')
        connection.commit()

def init_fb():
    response = requests.get(f'{FIREBASE_URL}/cells.json')
    if response.status_code != 200 or not response.json():
        requests.put(f'{FIREBASE_URL}/cells.json', json={})

def get_db_connection():
    return sqlite3.connect(DATABASE_URI)

def get_firebase_data():
    response = requests.get(f'{FIREBASE_URL}/cells.json')
    if response.status_code == 200:
        return response.json() or {}
    else:
        return None

def write_to_firebase(cell_id, formula):
    firebase_data = get_firebase_data()
    is_new_cell = cell_id not in firebase_data
    response = requests.put(f'{FIREBASE_URL}/cells/{cell_id}.json', json={'formula': formula})
    if response.status_code == 200:
        return response.status_code, is_new_cell
    else:
        return response.status_code, is_new_cell

@app.route('/cells/<string:cell_id>', methods=['PUT'])
def create_or_update_cell(cell_id):
    if not request.is_json:
        return "", 400
    js = request.get_json()
    if 'id' not in js or js['id'] != cell_id:
        return "", 400
    if 'formula' not in js:
        return "", 400
    formula = js['formula']
    if '-r' in sys.argv and sys.argv[sys.argv.index('-r')+1] == 'firebase':
        status_code, is_new_cell = write_to_firebase(cell_id, formula)
        if status_code == 200:
            return '', 201 if is_new_cell else 204
        else:
            return '', 500
    else:
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM cells WHERE id=?", (cell_id,))
            existing_cell = cursor.fetchone()
            if existing_cell:
                cursor.execute("UPDATE cells SET formula=? WHERE id=?", (formula, cell_id))
                connection.commit()
                response_code = 204
            else:
                cursor.execute("INSERT INTO cells (id, formula) VALUES (?, ?)", (cell_id, formula))
                connection.commit()
                response_code = 201
        except sqlite3.IntegrityError:
            connection.close()
            return '', 400
        finally:
            connection.close()
        return '', response_code

@app.route('/cells/<string:cell_id>', methods=['GET'])
def read_cell(cell_id):
    try:
        if '-r' in sys.argv and sys.argv[sys.argv.index('-r')+1] == 'firebase':
            firebase_data = get_firebase_data()
            if firebase_data and cell_id in firebase_data:
                cell_values = {key: val['formula'] for key, val in firebase_data.items() if 'formula' in val}
                formula = firebase_data[cell_id]['formula']
                evaluated_formula = evaluate_formula(formula, cell_values)
                # Ensure response is formatted as {"formula":"<evaluated_formula>"}
                return jsonify({'formula': str(evaluated_formula)}), 200
            else:
                return "", 404
        else:
            cell_values = {}
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, formula FROM cells")
            rows = cursor.fetchall()
            for row in rows:
                cell_values[row[0]] = row[1]  # Store raw formulas
            formula = cell_values.get(cell_id)
            if formula:
                evaluated_formula = evaluate_formula(formula, cell_values)  # Adjust to handle raw formula
                return jsonify({'formula': str(evaluated_formula), 'id': cell_id}), 200
            else:
                return "", 404
    except Exception as e:
        app.logger.error(f"Error during cell read operation: {e}")
        return "", 500
    finally:
        if 'connection' in locals():
            connection.close()

@app.route('/cells', methods=['GET'])
def list_cells():
    if '-r' in sys.argv and sys.argv[sys.argv.index('-r')+1] == 'firebase':
        firebase_data = get_firebase_data()
        if firebase_data is None:
            return jsonify({'error': 'Failed to retrieve data'}), 500
        cells = list(firebase_data.keys()) if firebase_data else []
        return jsonify(cells), 200
    else:
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM cells")
            cells = [row[0] for row in cursor.fetchall()]
            return jsonify(cells), 200
        finally:
            connection.close()

@app.route('/cells/<string:cell_id>', methods=['DELETE'])
def delete_cell(cell_id):
    if '-r' in sys.argv and sys.argv[sys.argv.index('-r')+1] == 'firebase':
        response = requests.delete(f'{FIREBASE_URL}/cells/{cell_id}.json')
        if response.status_code == 200:
            return '', 204
        else:
            return '', 500

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM cells WHERE id=?", (cell_id,))
        connection.commit()
        return '', 204
    finally:
        connection.close()

def evaluate_formula(formula, cell_values):
    # Function to resolve cell reference to its evaluated value
    def resolve_reference(match):
        ref_id = match.group(1)
        if ref_id in cell_values:
            # Recursively evaluate referenced formula
            return str(evaluate_formula(cell_values[ref_id], cell_values))
        else:
            return "0"  # Return 0 if reference is unresolved

    resolved_formula = re.sub(r'([A-Z]+\d+)', resolve_reference, formula)
    try:
        return eval(resolved_formula)
    except Exception as e:
        raise Exception(f"Error evaluating formula: {e}")

if __name__ == '__main__':
    if '-r' in sys.argv and sys.argv[sys.argv.index('-r')+1] == 'firebase':
        init_fb()
        app.run(host="localhost", port=3000)
    else:
        init_db()
        app.run(host="localhost", port=3000)
