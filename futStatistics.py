from flask import Flask, render_template, request, jsonify, send_file
import requests
import csv
import io
from waitress import serve
from monteCarlo import calculate_statistics
from collections import OrderedDict
import json

app = Flask(__name__)

leagues = {
    'BR': 268,
    'ES': 87,
    'ENG': 47,
    'IT': 55,
    'DE': 54
}


# Route for homepage with iframe
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/iframe')
def iframe_page():
    return render_template('iframe.html')


# Route for retrieving teams
@app.route('/get_teams', methods=['GET'])
def get_teams():
    country = request.args.get('country', 'BR')
    league_id = leagues.get(country, 268)
    try:
        response = requests.get(f'https://www.fotmob.com/api/leagues?id={league_id}')
        data = response.json()
        teams = data['table'][0]['data']['table']['all']
        teams = add_type_to_teams(teams)

        # return team_data
        return (populate_json_to_print(teams, 'teams'))
    except Exception as e:
        return jsonify({'error': str(e)})


def add_type_to_teams(teams):
    team_data = []
    num_teams = len(teams)
    for index, team in enumerate(teams):
        position = index + 1  # Position is 1-based
        # Calculate Type value based on position
        if position <= 4:
            type_value = 5
        elif position <= 8:
            type_value = 4
        elif position <= 12:
            type_value = 3
        elif position <= 16:
            type_value = 2
        else:
            type_value = 1

        team_data.append({
            'id': team['id'],
            'idx': position,
            'name': team['shortName'],
            'pts': team['pts'],  # Assuming this field exists
            'type': type_value  # Add calculated Type value
        })
    return team_data


def populate_json_to_print(data, activity):
    # icon = f'<img src="https://images.fotmob.com/image_resources/logo/teamlogo/${item.id}_small.png" alt="Team Logo" width="30">'
    formatted_data = []
    if activity == 'teams':
        for team in data:
            formatted_data.append(OrderedDict({
                'Position': team['idx'],
                'Time': f'https://images.fotmob.com/image_resources/logo/teamlogo/{team["id"]}_small.png',
                'Points': team['pts'],  # Assuming this field exists
                'type': team['type'],  # Add calculated Type value
                'Name': team["name"],
                'id': team['id']
            }))
    elif activity == 'games':
        formatted_data = [{
            'Time_Home': f'https://images.fotmob.com/image_resources/logo/teamlogo/{match["home"]["id"]}_small.png',
            'Name_Home': match['home']['shortName'],
            'score': match['status'].get('scoreStr', 'N/A'),  # If scoreStr doesn't exist, set it to 'N/A'
            'Name_Away': match['away']['shortName'],
            'Time_Away': f'https://images.fotmob.com/image_resources/logo/teamlogo/{match["away"]["id"]}_small.png'
        } for match in data]

    json_data = json.dumps(formatted_data)
    #return json_data
    return formatted_data


# Route for retrieving games
@app.route('/get_games', methods=['GET'])
def get_games(country=None):
    if not country:
        country = request.args.get('country', 'BR')
    league_id = leagues.get(country, 268)
    try:
        response = requests.get(f'https://www.fotmob.com/api/leagues?id={league_id}')
        data = response.json()
        matches = data['matches']['allMatches']
        game_data = populate_json_to_print(matches, 'games')

        # return jsonify(game_data)
        return game_data
    except Exception as e:
        return jsonify({'error': str(e)})


# Load teams from CSV
@app.route('/load_teams_from_csv', methods=['POST'])
def load_teams_from_csv():
    file = request.files.get('file')
    country = request.args.get('country', 'BR')

    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    csv_data = file.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(csv_data))
    csv_teams = list(reader)

    # Fetch teams from the get_teams endpoint
    league_id = leagues.get(country, 268)
    response = requests.get(f'https://www.fotmob.com/api/leagues?id={league_id}')
    data = response.json()
    teams = data['table'][0]['data']['table']['all']

    # Merge CSV 'type' data with the team data fetched from the API
    for team in teams:
        matching_team = next((csv_team for csv_team in csv_teams if csv_team['id'] == str(team['id'])), None)
        if matching_team:
            team['type'] = int(matching_team['type'])  # Replace type from CSV
        # else: # If no CSV type is found,do nothing

    return (populate_json_to_print(teams, 'teams'))
    # return teams


# Save teams to CSV
@app.route('/save_teams_to_csv', methods=['POST'])
def save_teams_to_csv():
    teams = request.json.get('teams', [])

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'type'])  # Write header
    for team in teams:
        writer.writerow([team['id'], team['type']])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True,
                     download_name='teams.csv')


def run_and_populate_stats():
    teams = load_teams_from_csv()
    games = get_games()
    return calculate_statistics(teams, games)


@app.route('/export', methods=['POST'])
def export_table():
    teams = get_teams()
    games = get_games()
    data = calculate_statistics(teams, games)
    print(data)

    return data


@app.route('/statistics', methods=['POST'])
def populate_statistics():
    csv_teams = request.json.get('teams', [])
    country_json = request.json.get('country', [])
    country = country_json['country']
    league_id = leagues.get(country, 268)
    response = requests.get(f'https://www.fotmob.com/api/leagues?id={league_id}')
    data = response.json()
    teams = data['table'][0]['data']['table']['all']

    # Merge CSV 'type' data with the team data fetched from the API
    for team in teams:
        matching_team = next((csv_team for csv_team in csv_teams if csv_team['id'] == str(team['id'])), None)
        if matching_team:
            team['type'] = int(matching_team['type'])  # Replace type from CSV
        # else: # If no CSV type is found,do nothing

    games = get_games(country)
    data = calculate_statistics(teams, games, country)
    print(data)

    return data


if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8000)
    app.run(debug=False)
