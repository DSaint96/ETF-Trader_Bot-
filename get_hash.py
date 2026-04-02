import schwab, os
from dotenv import load_dotenv
load_dotenv()
token_path = os.getenv('SCHWAB_TOKEN_PATH', 'schwab_token.json')
client = schwab.auth.client_from_token_file(token_path, os.getenv('SCHWAB_APP_KEY'), os.getenv('SCHWAB_APP_SECRET'))
response = client.get_account_numbers()
print(response.json())
