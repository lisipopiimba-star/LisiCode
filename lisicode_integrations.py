# -*- coding: utf-8 -*-
"""Real Gmail, Google Drive and Telegram integrations for LisiCode.
Google OAuth uses a Desktop OAuth client JSON supplied by the user.
Telegram uses the official MTProto API through Telethon.
"""
import asyncio, json, os, time, urllib.parse, urllib.request, urllib.error, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = Path.home()/'.lisicode'
GOOGLE_TOKEN = BASE/'google_token.json'
TELEGRAM_SESSION = BASE/'telegram_session'

SCOPES = [
 'https://www.googleapis.com/auth/gmail.readonly',
 'https://www.googleapis.com/auth/gmail.send',
 'https://www.googleapis.com/auth/drive.readonly',
 'https://www.googleapis.com/auth/drive.file',
]

def _request(url, token=None, method='GET', payload=None, headers=None):
    h=dict(headers or {})
    if token: h['Authorization']='Bearer '+token
    data=None
    if payload is not None:
        if isinstance(payload, bytes): data=payload
        else: data=json.dumps(payload).encode(); h['Content-Type']='application/json'
    req=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read()
            if not raw:return {}
            c=r.headers.get('Content-Type','')
            return json.loads(raw.decode('utf-8')) if 'json' in c or raw[:1] in (b'{',b'[') else raw
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Google API HTTP {e.code}: {e.read().decode("utf-8","replace")[:800]}')

def google_connected():
    try:
        d=json.loads(GOOGLE_TOKEN.read_text(encoding='utf-8'))
        return bool(d.get('refresh_token') or (d.get('access_token') and d.get('expires_at',0)>time.time()+30))
    except Exception:return False

def connect_google(credentials_path, ask_input):
    p=Path(credentials_path).expanduser()
    if not p.is_file(): raise FileNotFoundError('Не найден OAuth credentials JSON: '+str(p))
    raw=json.loads(p.read_text(encoding='utf-8'))
    c=raw.get('installed') or raw.get('web')
    if not c or not c.get('client_id') or not c.get('client_secret'):
        raise ValueError('Нужен OAuth Client ID типа Desktop app (credentials.json из Google Cloud).')
    client_id,secret=c['client_id'],c['client_secret']
    state=os.urandom(18).hex(); result={}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get('state',[''])[0]!=state:
                self.send_response(400); self.end_headers(); self.wfile.write(b'Invalid state'); return
            result.update({k:v[0] for k,v in q.items()})
            body=b'Authorization received. You can close this window and return to LisiCode.'
            self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*a):pass
    server=HTTPServer(('127.0.0.1',0),Handler); server.timeout=180
    port=server.server_address[1]; redirect=f'http://127.0.0.1:{port}/'
    params={'client_id':client_id,'redirect_uri':redirect,'response_type':'code','scope':' '.join(SCOPES),'access_type':'offline','prompt':'consent','state':state}
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params)
    print('Откроется браузер Google для разрешений Gmail (чтение/отправка) и Drive (чтение/создание файлов).')
    print('Если браузер не открылся, скопируй адрес из следующей строки:'); print(url)
    webbrowser.open(url)
    deadline=time.time()+180
    while time.time()<deadline and not result: server.handle_request()
    server.server_close()
    if 'code' not in result: raise TimeoutError('Google OAuth не завершён или отменён.')
    form=urllib.parse.urlencode({'code':result['code'],'client_id':client_id,'client_secret':secret,'redirect_uri':redirect,'grant_type':'authorization_code'}).encode()
    req=urllib.request.Request('https://oauth2.googleapis.com/token',data=form,headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req,timeout=45) as r: token=json.loads(r.read())
    token['expires_at']=time.time()+int(token.get('expires_in',3600)); token['client_id']=client_id; token['client_secret']=secret
    BASE.mkdir(parents=True,exist_ok=True); GOOGLE_TOKEN.write_text(json.dumps(token),encoding='utf-8')
    try:os.chmod(GOOGLE_TOKEN,0o600)
    except Exception:pass
    return True

def google_token():
    if not GOOGLE_TOKEN.exists():raise RuntimeError('Google не подключён. Выполни /connections gmail или /connections drive.')
    d=json.loads(GOOGLE_TOKEN.read_text(encoding='utf-8'))
    if d.get('expires_at',0)<time.time()+60:
        if not d.get('refresh_token'):raise RuntimeError('Google token истёк. Отключи и подключи Google заново.')
        form=urllib.parse.urlencode({'client_id':d['client_id'],'client_secret':d['client_secret'],'refresh_token':d['refresh_token'],'grant_type':'refresh_token'}).encode()
        req=urllib.request.Request('https://oauth2.googleapis.com/token',data=form,headers={'Content-Type':'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req,timeout=45) as r: fresh=json.loads(r.read())
        d.update(fresh); d['expires_at']=time.time()+int(fresh.get('expires_in',3600)); GOOGLE_TOKEN.write_text(json.dumps(d),encoding='utf-8')
        try:os.chmod(GOOGLE_TOKEN,0o600)
        except Exception:pass
    return d['access_token']

def gmail_search(query='newer_than:30d', limit=10):
    t=google_token(); q=urllib.parse.urlencode({'q':query,'maxResults':max(1,min(int(limit),30))})
    data=_request('https://gmail.googleapis.com/gmail/v1/users/me/messages?'+q,t)
    out=[]
    for m in data.get('messages',[]):
        msg=_request('https://gmail.googleapis.com/gmail/v1/users/me/messages/'+m['id']+'?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date',t)
        h={x['name'].lower():x['value'] for x in msg.get('payload',{}).get('headers',[])}
        out.append({'id':m['id'],'threadId':msg.get('threadId'),'from':h.get('from',''),'subject':h.get('subject',''),'date':h.get('date',''),'snippet':msg.get('snippet','')})
    return out

def gmail_read(message_id):
    t=google_token(); m=_request('https://gmail.googleapis.com/gmail/v1/users/me/messages/'+urllib.parse.quote(message_id,safe='')+'?format=full',t)
    def decode(part):
        import base64
        body=part.get('body',{}).get('data')
        if body:
            try:return base64.urlsafe_b64decode(body+'===').decode('utf-8','replace')
            except Exception:return ''
        return '\n'.join(decode(x) for x in part.get('parts',[]))
    h={x['name'].lower():x['value'] for x in m.get('payload',{}).get('headers',[])}
    return {'id':message_id,'from':h.get('from',''),'to':h.get('to',''),'subject':h.get('subject',''),'date':h.get('date',''),'body':decode(m.get('payload',{}))[:20000]}

def gmail_send(to, subject, body):
    import base64
    raw=f'To: {to}\r\nSubject: {subject}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset="UTF-8"\r\n\r\n{body}'
    data=base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')
    return _request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',google_token(),'POST',{'raw':data})

def drive_search(query='',limit=20):
    t=google_token(); q="trashed=false"
    if query:q+=f" and name contains '{query.replace(chr(39), chr(92)+chr(39))}'"
    params=urllib.parse.urlencode({'q':q,'pageSize':max(1,min(int(limit),50)),'fields':'files(id,name,mimeType,modifiedTime,webViewLink,size)'})
    return _request('https://www.googleapis.com/drive/v3/files?'+params,t).get('files',[])

def drive_read(file_id):
    t=google_token(); meta=_request('https://www.googleapis.com/drive/v3/files/'+urllib.parse.quote(file_id,safe='')+'?fields=id,name,mimeType',t)
    if meta.get('mimeType')=='application/vnd.google-apps.document':
        data=_request('https://www.googleapis.com/drive/v3/files/'+urllib.parse.quote(file_id,safe='')+'/export?mimeType=text/plain',t)
    else:data=_request('https://www.googleapis.com/drive/v3/files/'+urllib.parse.quote(file_id,safe='')+'?alt=media',t)
    if isinstance(data,bytes):data=data.decode('utf-8','replace')
    return {'metadata':meta,'content':str(data)[:30000]}

def drive_create(name,content,mime_type='text/plain'):
    boundary='lisi_'+os.urandom(8).hex(); meta=json.dumps({'name':name,'mimeType':mime_type}).encode()
    body=(b'--'+boundary.encode()+b'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+meta+b'\r\n--'+boundary.encode()+b'\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'+content.encode()+b'\r\n--'+boundary.encode()+b'--')
    return _request('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink',google_token(),'POST',body,{'Content-Type':'multipart/related; boundary='+boundary})

async def _telegram_client():
    try: from telethon import TelegramClient
    except ImportError: raise RuntimeError('Не установлен Telethon. Запусти pip install -r requirements.txt.')
    cfg=json.loads((BASE/'config.json').read_text(encoding='utf-8'))
    api_id=int(cfg['telegram_api_id']); api_hash=cfg['telegram_api_hash']
    client=TelegramClient(str(TELEGRAM_SESSION),api_id,api_hash)
    await client.connect()
    if not await client.is_user_authorized(): raise RuntimeError('Telegram не авторизован. Выполни /connections telegram login.')
    return client

def telegram_chats(limit=30):
    from telethon.tl.types import User, Chat, Channel
    async def run():
        c=await _telegram_client()
        try:
            rows=[]
            async for d in c.iter_dialogs(limit=max(1,min(int(limit),50))): rows.append({'id':d.id,'name':d.name,'unread':d.unread_count,'is_user':bool(getattr(d.entity,'bot',False) is False and isinstance(d.entity,User))})
            return rows
        finally: await c.disconnect()
    return asyncio.run(run())

def telegram_history(chat,limit=30):
    async def run():
        c=await _telegram_client()
        try:
            target=int(chat) if str(chat).lstrip('-').isdigit() else chat
            ent=await c.get_entity(target); rows=[]
            async for m in c.iter_messages(ent,limit=max(1,min(int(limit),100))): rows.append({'id':m.id,'date':str(m.date),'sender':getattr(m.sender,'first_name',None) or getattr(m.sender,'title',None) or str(m.sender_id),'text':m.message or ''})
            return list(reversed(rows))
        finally: await c.disconnect()
    return asyncio.run(run())

def telegram_send(chat,text_value,reply_to=None):
    async def run():
        c=await _telegram_client()
        try:
            target=int(chat) if str(chat).lstrip('-').isdigit() else chat
            ent=await c.get_entity(target); m=await c.send_message(ent,text_value,reply_to=reply_to); return {'id':m.id,'chat':str(chat),'text':m.message}
        finally: await c.disconnect()
    return asyncio.run(run())

def telegram_connect(api_id,api_hash,phone,code_provider,password_provider):
    try:
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
    except ImportError: raise RuntimeError('Не установлен Telethon. Запусти pip install -r requirements.txt.')
    async def run():
        c=TelegramClient(str(TELEGRAM_SESSION),int(api_id),api_hash); await c.connect()
        try:
            if not await c.is_user_authorized():
                sent=await c.send_code_request(phone); code=code_provider('Код из Telegram: ')
                try: await c.sign_in(phone,code,phone_code_hash=sent.phone_code_hash)
                except SessionPasswordNeededError:
                    await c.sign_in(password=password_provider('Пароль двухэтапной проверки (если включён): '))
            me=await c.get_me(); return {'id':me.id,'name':getattr(me,'first_name',''),'username':getattr(me,'username',None)}
        finally: await c.disconnect()
    return asyncio.run(run())

# ElevenLabs text-to-speech integration (REST API; no SDK dependency required).
ELEVENLABS_API = 'https://api.elevenlabs.io/v1'

def elevenlabs_request(path, api_key, method='GET', payload=None, raw=False):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'xi-api-key': api_key, 'Accept': 'audio/mpeg' if raw else 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(ELEVENLABS_API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            content = response.read()
            return content if raw else json.loads(content.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')[:1000]
        raise RuntimeError(f'ElevenLabs API HTTP {exc.code}: {detail}')
    except urllib.error.URLError as exc:
        raise RuntimeError(f'ElevenLabs API недоступен: {exc.reason}')

def elevenlabs_voices(api_key, limit=50):
    data = elevenlabs_request('/voices', api_key)
    return [{'name': v.get('name', ''), 'voice_id': v.get('voice_id', ''), 'category': v.get('category', '')}
            for v in data.get('voices', [])[:max(1, min(int(limit), 100))]]

def elevenlabs_tts(api_key, text, voice_id, model_id='eleven_multilingual_v2'):
    if not text or len(text) > 10000:
        raise ValueError('Текст должен содержать от 1 до 10000 символов.')
    if not voice_id or len(voice_id) > 128:
        raise ValueError('Укажи корректный ElevenLabs voice_id.')
    payload = {'text': text, 'model_id': model_id}
    return elevenlabs_request('/text-to-speech/' + urllib.parse.quote(voice_id, safe=''), api_key,
                              method='POST', payload=payload, raw=True)
