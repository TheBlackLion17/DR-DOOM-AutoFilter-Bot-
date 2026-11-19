import os
from dotenv import load_dotenv
load_dotenv()

CFG = {k: os.getenv(k, '') for k in ('API_ID','API_HASH','BOT_TOKEN','BOT_USERNAME','ADMINS','DB_HOST','DB_PORT','DB_USER','DB_PASSWORD','DB_NAME','SOURCE_CHANNELS','FORCE_SUB_CHANNEL','FORCE_SUB_LINK','DELETE_SECONDS','RESULTS_PER_PAGE','USER_SESSION')}
CFG['DB_HOST'] = CFG['DB_HOST'] or '127.0.0.1'
CFG['DB_PORT'] = CFG['DB_PORT'] or '3306'
CFG['DB_NAME'] = CFG['DB_NAME'] or 'autofilter'
ADMINS = {int(x.strip()) for x in CFG['ADMINS'].split(',') if x.strip()}
CHANNELS = {int(x.strip()) for x in CFG['SOURCE_CHANNELS'].split(',') if x.strip()}
FORCE_CHANNEL = int(CFG['FORCE_SUB_CHANNEL'] or '0')
DELETE_SECONDS = max(30, int(CFG['DELETE_SECONDS'] or '300'))
PAGE_SIZE = max(1, min(10, int(CFG['RESULTS_PER_PAGE'] or '8')))
for required in ('API_ID','API_HASH','BOT_TOKEN','BOT_USERNAME','DB_USER','DB_PASSWORD'):
    if not CFG[required]:
        raise RuntimeError(f'Missing {required} in .env')
