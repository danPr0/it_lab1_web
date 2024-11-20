import re
import json

from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)


DB_FILEPATH = 'data/test_db.json'


def load_db(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def save_db(filepath):
    with open(filepath, 'w') as f:
        json.dump(databases, f)


databases = load_db(DB_FILEPATH)
# databases = {}


@app.route('/')
def index():
    return render_template('index.html', databases=databases)


@app.route('/databases', methods=['POST'])
def create_database():
    db_name = request.form.get('name')
    if not db_name:
        return render_template('error.html', message="Database name is required")
    if db_name in databases:
        return render_template('error.html', message=f"Database '{db_name}' already exists")
    databases[db_name] = {}
    save_db(DB_FILEPATH)
    return redirect(url_for('index'))


@app.route('/databases', methods=['GET'])
def list_databases():
    return jsonify(list(databases.keys()))


@app.route('/databases/<db_name>/delete', methods=['POST'])
def delete_database(db_name):
    if db_name not in databases:
        return render_template('error.html', message=f"Database '{db_name}' not found")
    del databases[db_name]
    save_db(DB_FILEPATH)
    return redirect(url_for('index'))


@app.route('/databases/<db_name>')
def database_page(db_name):
    if db_name not in databases:
        return render_template('error.html', message=f"Database '{db_name}' not found")
    return render_template('database.html', db_name=db_name, tables=databases[db_name])


@app.route('/databases/<db_name>/tables', methods=['POST'])
def create_table(db_name):
    if db_name not in databases:
        return render_template('error.html', message=f"Database '{db_name}' not found")
    table_name = request.form.get('name')
    schema = request.form.get('schema') or '{}'  # Схема вводиться у вигляді JSON
    if not table_name:
        return render_template('error.html', message="Table name and schema are required")
    if table_name in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' already exists")
    try:
        schema_dict = eval(schema)  # Преобразуємо JSON у словник
        databases[db_name][table_name] = {"schema": schema_dict, "rows": []}
    except Exception as e:
        return render_template('error.html', message=f"Invalid schema format: {e}")
    save_db(DB_FILEPATH)
    return redirect(url_for('database_page', db_name=db_name))


@app.route('/databases/<db_name>/tables', methods=['GET'])
def list_tables(db_name):
    if db_name not in databases:
        return jsonify({"error": f"Database '{db_name}' not found"}), 404
    return jsonify(list(databases[db_name].keys()))


@app.route('/databases/<db_name>/tables/<table_name>/delete', methods=['POST'])
def delete_table(db_name, table_name):
    if db_name not in databases or table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found in database '{db_name}'")
    del databases[db_name][table_name]
    save_db(DB_FILEPATH)
    return redirect(url_for('database_page', db_name=db_name))


@app.route('/databases/<db_name>/tables/<table_name>')
def table_page(db_name, table_name):
    if db_name not in databases or table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found in database '{db_name}'")
    table = databases[db_name][table_name]
    return render_template('table.html', db_name=db_name, table_name=table_name, table=table)


# Add a column to a table with enum support
@app.route('/databases/<db_name>/tables/<table_name>/columns', methods=['POST'])
def add_column(db_name, table_name):
    if db_name not in databases:
        return render_template('error.html', message=f"Database '{db_name}' not found")
    if table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found")

    column_name = request.form.get('name')
    column_type = request.form.get('type')
    enum_values = request.form.get('enum_values')  # Values provided as a comma-separated list

    if not column_name or not column_type:
        return render_template('error.html', message="Column name and type are required")

    table = databases[db_name][table_name]
    if column_name in table["schema"]:
        return render_template('error.html', message=f"Column '{column_name}' already exists in table '{table_name}'")

    if column_type == "enum" and enum_values:
        # Split and clean the enum values
        enum_values_list = [value.strip() for value in enum_values.split(',') if value.strip()]
        if not enum_values_list:
            return render_template('error.html', message="Enum values cannot be empty")
        # Add enum values to schema metadata
        table["schema"][f"{column_name}_values"] = enum_values_list

    # Add the column to the schema
    table["schema"][column_name] = column_type

    # Add default None value to all existing rows
    for row in table["rows"]:
        row[column_name] = None

    return redirect(url_for('table_page', db_name=db_name, table_name=table_name))


@app.route('/databases/<db_name>/tables/<table_name>/columns/<column_name>/delete', methods=['POST'])
def delete_column(db_name, table_name, column_name):
    if db_name not in databases:
        return render_template('error.html', message=f"Database '{db_name}' not found")
    if table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found")

    table = databases[db_name][table_name]
    if column_name not in table["schema"]:
        return render_template('error.html', message=f"Column '{column_name}' not found in table '{table_name}'")

    del table["schema"][column_name]

    for row in table["rows"]:
        if column_name in row:
            del row[column_name]

    save_db(DB_FILEPATH)
    return redirect(url_for('table_page', db_name=db_name, table_name=table_name))


@app.route('/databases/<db_name>/tables/<table_name>/rows', methods=['POST'])
def add_row(db_name, table_name):
    if db_name not in databases or table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found in database '{db_name}'")

    table = databases[db_name][table_name]
    new_row = {}
    for column, column_type in table["schema"].items():
        value = request.form.get(column)
        if column_type == "email":
            if not is_valid_email(value):
                return render_template('error.html', message=f"Invalid email format for column '{column}'")
        elif column_type == "enum":
            allowed_values = table["schema"].get(f"{column}_values", [])
            if value not in allowed_values:
                return render_template('error.html', message=f"Invalid value for enum column '{column}'. Allowed values: {allowed_values}")
        elif column_type == "int":
            try:
                value = int(value)
            except ValueError:
                return render_template('error.html', message=f"Invalid integer value for column '{column}'")
        elif column_type == "float":
            try:
                value = float(value)
            except ValueError:
                return render_template('error.html', message=f"Invalid float value for column '{column}'")
        new_row[column] = value

    table["rows"].append(new_row)
    save_db(DB_FILEPATH)
    return redirect(url_for('table_page', db_name=db_name, table_name=table_name))


@app.route('/databases/<db_name>/tables/<table_name>/rows', methods=['GET'])
def list_rows(db_name, table_name):
    if db_name not in databases:
        return jsonify({"error": f"Database '{db_name}' not found"}), 404
    if table_name not in databases[db_name]:
        return jsonify({"error": f"Table '{table_name}' not found in database '{db_name}'"}), 404
    return jsonify(databases[db_name][table_name]["rows"])


@app.route('/databases/<db_name>/tables/<table_name>/rows/<int:row_id>', methods=['POST'])
def update_row(db_name, table_name, row_id):
    if db_name not in databases or table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found in database '{db_name}'")

    table = databases[db_name][table_name]
    if row_id < 0 or row_id >= len(table["rows"]):
        return render_template('error.html', message=f"Row ID '{row_id}' is out of range")

    row = table["rows"][row_id]
    for column, column_type in table["schema"].items():
        value = request.form.get(column)
        if column_type == "email" and not is_valid_email(value):
            return render_template('error.html', message=f"Invalid email format for column '{column}'")
        elif column_type == "enum":
            allowed_values = table["schema"].get(f"{column}_values", [])
            if value not in allowed_values:
                return render_template('error.html', message=f"Invalid value for enum column '{column}'. Allowed values: {allowed_values}")
        elif column_type == "int":
            try:
                value = int(value)
            except ValueError:
                return render_template('error.html', message=f"Invalid integer value for column '{column}'")
        elif column_type == "float":
            try:
                value = float(value)
            except ValueError:
                return render_template('error.html', message=f"Invalid float value for column '{column}'")
        row[column] = value

    save_db(DB_FILEPATH)
    return redirect(url_for('table_page', db_name=db_name, table_name=table_name))


@app.route('/databases/<db_name>/tables/<table_name>/rows/<int:row_id>/delete', methods=['POST'])
def delete_row(db_name, table_name, row_id):
    if db_name not in databases or table_name not in databases[db_name]:
        return render_template('error.html', message=f"Table '{table_name}' not found in database '{db_name}'")

    table = databases[db_name][table_name]
    if row_id < 0 or row_id >= len(table["rows"]):
        return render_template('error.html', message=f"Row ID '{row_id}' is out of range")

    table["rows"].pop(row_id)
    save_db(DB_FILEPATH)
    return redirect(url_for('table_page', db_name=db_name, table_name=table_name))


def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)


if __name__ == '__main__':
    app.run(debug=True)
