import simplebot
import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError
from dropbox import DropboxOAuth2FlowNoRedirect
import zipfile
import base64
import psycopg2
import html
#Secure save storage to use in non persistent storage
DBXTOKEN = os.getenv('DBXTOKEN')
APP_KEY = os.getenv('APP_KEY')

if APP_KEY:
   auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, use_pkce=True, token_access_type='offline')

if DBXTOKEN:
   if APP_KEY:
      dbx = dropbox.Dropbox(oauth2_refresh_token=DBXTOKEN, app_key=APP_KEY)
   else:
      dbx = dropbox.Dropbox(DBXTOKEN)
   # Check that the access token is valid
   try:
      dbx.users_get_current_account()
   except AuthError:
       print("ERROR: Invalid access token; try re-generating an "
                "access token from the app console on the web.")

def save_bot_db():
    if DBXTOKEN:
       backup_db()
    elif DATABASE_URL:
       db_save()


def backup(backup_path):
    with open(backup_path, 'rb') as f:
        print("Uploading " + backup_path + " to Dropbox...")
        if backup_path.startswith('.'):
           dbx_backup_path = backup_path.replace('.','',1)
        else:
           dbx_backup_path =backup_path
        try:
            dbx.files_upload(f.read(), dbx_backup_path, mode=WriteMode('overwrite'))
        except ApiError as err:
            # This checks for the specific error where a user doesn't have
            # enough Dropbox space quota to upload this file
            if (err.error.is_path() and
                    err.error.get_path().reason.is_insufficient_space()):
                #sys.exit("ERROR: Cannot back up; insufficient space.")
                print("ERROR: Cannot back up; insufficient space.", err)
            elif err.user_message_text:
                print(err.user_message_text)
                sys.exit()
            else:
                print(err)
                sys.exit()

def db_init():
    try:
       con = psycopg2.connect(DATABASE_URL)
       cur = con.cursor()
       cur.execute("SELECT * FROM information_schema.tables WHERE table_name=%s", ('simplebot_db',))
       if bool(cur.rowcount):
          print("La tabla existe!")
       else:
          print("La tabla no existe, creando...")
          cur.execute("CREATE TABLE simplebot_db (id bigint PRIMARY KEY, name TEXT, data BYTEA)")
          con.commit()
          cur.execute("ALTER TABLE simplebot_db ALTER COLUMN data SET STORAGE EXTERNAL")
          con.commit()
       cur.close()
    except Exception as error:
       print('Cause: {}'.format(error))
    finally:
       if con is not None:
           con.close()
           print('Database connection closed.')

def db_save():
    try:
       con = psycopg2.connect(DATABASE_URL)
       cur = con.cursor()
       print("Salvando a postgres...")
       zipfile = zipdir(bot_home+'/.simplebot/', encode_bot_addr+'.zip')
       bin = open(zipfile, 'rb').read()
       #cur.execute("TRUNCATE simplebot_db")
       #con.commit()
       cur.execute("INSERT INTO simplebot_db(id,name,data) VALUES(%s,%s,%s) ON CONFLICT (id) DO UPDATE SET name = excluded.name, data = excluded.data", (0,encode_bot_addr, psycopg2.Binary(bin)))
       con.commit()
       cur.close()
    except Exception as error:
       print('Cause: {}'.format(error))
    finally:
       if con is not None:
           con.close()
           print('Database connection closed.')

def zipdir(dir_path,file_path):
    zf = zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_LZMA)
    for dirname, subdirs, files in os.walk(dir_path):
        if dirname.endswith('account.db-blobs'):
           continue
        zf.write(dirname)
        print(dirname)
        for filename in files:
            if filename=='bot.db-journal':
               continue
            print(filename)
            zf.write(os.path.join(dirname, filename))
    zf.close()
    return file_path

def savelogin(bot):
    bot.set('LOGINDB',json.dumps(logindb))
    save_bot_db()

def saveautochats(bot):
    bot.set('AUTOCHATSDB',json.dumps(autochatsdb))
    save_bot_db()

def fixautochats(bot):
    cids = []
    dchats = bot.account.get_chats()
    for c in dchats:
        cids.append(str(c.id))
    #print('Chats guardados: '+str(cids))
    tmpdict = copy.deepcopy(autochatsdb)
    for (key, value) in tmpdict.items():
        for (inkey, invalue) in value.items():
            if str(inkey) not in cids:
               print('El chat '+str(inkey)+' no existe en el bot')
               del autochatsdb[key][inkey]

def backup_db():
    #bot.account.stop_io()
    print('Backup...')
    zipfile = zipdir(bot_home+'/.simplebot/', encode_bot_addr+'.zip')
    #bot.account.start_io()
    if os.path.getsize('./'+zipfile)>22:
       backup('./'+zipfile)
    else:
       print('Invalid zip file!')
    os.remove('./'+zipfile)

#end