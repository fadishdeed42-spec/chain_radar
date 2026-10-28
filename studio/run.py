"""GitHub runner for automatic Shorts. Called by .github/workflows/short.yml:
    python studio/run.py voice  JOB_ID   -> house voice (Chatterbox + am_liam, best take per scene) -> audio preview in Telegram
    python studio/run.py render JOB_ID   -> timing, real chart data, video (parallel), sfx, mix -> finished Short in Telegram
Job files live in jobs/<id>/ (storyboard.json written by the bot; outputs committed back so the next stage can use them)."""
import os, sys, json, re, time, subprocess, datetime, glob
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story

TOKEN, CHAT = os.environ.get('TELEGRAM_TOKEN', ''), os.environ.get('TELEGRAM_CHAT_ID', '')
E = lambda s: str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def tg(method, data, files=None):
    if not TOKEN:
        print('TG', method, data.get('caption') or data.get('text')); return None
    try:
        r = requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}', data={'chat_id': CHAT, 'parse_mode': 'HTML', **data}, files=files, timeout=300)
        if not r.ok: print('telegram', r.status_code, r.text[:200])
        return r
    except Exception as e:
        print('telegram fail', e)


def kb(rows):
    return json.dumps({'inline_keyboard': [[{'text': a, 'callback_data': b} for a, b in row] for row in rows]})


def sh(cmd, **kw):
    print('$', cmd if isinstance(cmd, str) else ' '.join(cmd))
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=True, **kw)


# ---------------------------------------------------------------- voice stage
def status(jid, state, **kw):
    """jobs/<id>/status.json: what the Studio app shows (draft, voice_running, voice_ready, rendering, done, failed)."""
    p = f'jobs/{jid}/status.json'
    try:
        st = json.load(open(p))
    except Exception:
        st = {}
    st.update({'state': state, 't': int(time.time()), **kw})
    json.dump(st, open(p, 'w'))


def drop_chart(sb, why):
    print('chart dropped:', why)
    for s in sb['scenes']:
        if s['visual']['type'] == 'chart':
            s['visual'] = {'type': 'title', 'text': s['visual'].get('label') or s['line'].split('.')[0][:22], 'icon': 'bitcoin'}
    sb['chart'] = None


def voice(jid):
    d = f'jobs/{jid}'
    sb, probs = story.check(json.load(open(f'{d}/storyboard.json')), strict=False)      # length was decided (or accepted) before the voice
    if sb.get('chart'):                                                   # real candles first: no data -> no chart and no "every chart" line
        D, src = daily(sb['chart']['symbol'], sb['chart']['start'], sb['chart']['end'])
        if D:
            json.dump(D, open(f'{d}/data.json', 'w')); sb['chart']['src'] = src
        else:
            drop_chart(sb, 'no candles for ' + sb['chart']['symbol'])
    vj, plan = story.voice_job(sb)
    vj['seed'] = int(sb.get('voice_seed', 7))
    json.dump(vj, open(f'{d}/voice.json', 'w'), indent=1)
    json.dump(plan, open(f'{d}/plan.json', 'w'))
    json.dump(sb, open(f'{d}/storyboard.json', 'w'), indent=1)
    import cvoice
    cvoice.run(f'{d}/voice.json')                                         # -> voice.wav, voice_words.srt, voicep.wav, voicep_words.srt, voice.log
    log = open(f'{d}/voice.log').read()
    wers = [float(x) for x in re.findall(r'wer (\d\.\d+)', log)]
    secs = float(re.findall(r'total ([\d.]+)s', log)[-1]) if re.findall(r'total ([\d.]+)s', log) else 0
    q = 'clean' if wers and min(wers) < .08 else 'check it'
    rate_ = story.measured_rate(d)
    words_ = sum(len(sp) for pl in json.load(open(f'{d}/plan.json')) for _, sp in pl)
    real = (words_ / rate_ if rate_ else secs) + story.END_PAD                  # same model the estimate uses, now with the real voice
    L_ = sb.get('length', 45); off = (real / L_ - 1) * 100
    lens = (f'\n⏱ <b>Real length: {story.mmss(real)}</b> (you picked {story.mmss(L_)}, {off:+.0f}%)'
            + ('' if story.WIN_LO - 1 <= off / 100 <= story.WIN_HI - 1 else '\n⚠️ Outside the length you asked for. Tap ✏️ Edit script to fix it, or continue.'))
    tg('sendAudio', {'caption': f'🎙 <b>Voice ready</b> · #{sb.get("ep", "")} {E(sb.get("title", ""))}\n{secs:.0f}s · tone: {sb["tone"]} · speech check: {q}{lens}'
                                + ('' if sb.get('chart') else ' · no chart for this story') + '\n\n'
                                '<b>Checkpoint 2:</b> listen, then make the video.',
                     'title': sb.get('title', 'Chain Secrets'), 'performer': 'Chain Secrets',
                     'reply_markup': kb([[('🎬 Make the video', f'sv:{jid}')], [('🔄 New voice take', f'sr:{jid}'), ('✏️ Edit script', f'se:{jid}')]])},
       files={'audio': open(f'{d}/voicep.mp3', 'rb')})
    status(jid, 'voice_ready', secs=round(secs), quality=q, real=round(real), rate=round(rate_ or 0, 3))
    if story.settings(sb).get('autorender'):
        open(f'{d}/autorender.flag', 'w').write('1')                      # the workflow starts the render after saving the voice
        tg('sendMessage', {'text': '🎬 Auto-render is on: the video starts now (~5–15 min).'})


# ---------------------------------------------------------------- chart data (real daily candles)
def daily(sym, start, end):
    s = datetime.datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(days=3)
    e = datetime.datetime.strptime(end, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=3)
    s, e = int(s.timestamp()), min(int(e.timestamp()), int(time.time()))
    rows, src = [], ''
    try:                                                                  # Bitstamp: BTC/ETH/LTC/XRP history back to 2011
        r = requests.get(f'https://www.bitstamp.net/api/v2/ohlc/{sym.lower()}usd/', params={'step': 86400, 'limit': min(1000, (e - s) // 86400 + 1), 'start': s}, timeout=20)
        rows = [(int(x['timestamp']), float(x['open']), float(x['high']), float(x['low']), float(x['close']), float(x['volume']))
                for x in r.json().get('data', {}).get('ohlc', [])]
        rows = [x for x in rows if s <= x[0] <= e]                         # only the requested window
        src = 'Bitstamp'
    except Exception as ex:
        print('bitstamp', ex)
    if len(rows) < 10:
        try:                                                              # Binance spot (public mirror), from 2017
            r = requests.get('https://data-api.binance.vision/api/v3/klines', params={'symbol': sym.upper() + 'USDT', 'interval': '1d',
                                                                                      'startTime': s * 1000, 'endTime': e * 1000, 'limit': 1000}, timeout=20)
            rows = [(k[0] // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in r.json()]
            src = 'Binance'
        except Exception as ex:
            print('binance', ex)
    if len(rows) < 10:
        try:                                                              # Coinbase, from 2015
            out = []
            for a in range(s, e, 300 * 86400):
                r = requests.get(f'https://api.exchange.coinbase.com/products/{sym.upper()}-USD/candles',
                                 params={'granularity': 86400, 'start': datetime.datetime.fromtimestamp(a, datetime.timezone.utc).isoformat(),
                                         'end': datetime.datetime.fromtimestamp(min(e, a + 299 * 86400), datetime.timezone.utc).isoformat()}, timeout=20)
                out += [(t, o, h, l, c, v) for t, l, h, o, c, v in r.json()]
            rows = sorted(set(out)); src = 'Coinbase'
        except Exception as ex:
            print('coinbase', ex)
    rows = sorted({r[0]: r for r in rows if s <= r[0] <= e}.values())
    if len(rows) > 220:                                                   # long stories: weekly candles keep the chart readable
        wk = []
        for i in range(0, len(rows), 7):
            g = rows[i:i + 7]
            wk.append((g[0][0], g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4], sum(x[5] for x in g)))
        rows = wk; src += ' weekly'
    if len(rows) < 10:
        return None, ''
    return {k: [r[n] for r in rows] for n, k in enumerate('tohlcv')}, src


# ---------------------------------------------------------------- render stage
def media_credits(d):
    try:
        import media
        return media.credits(d)
    except Exception:
        return ''


def render(jid):
    d = f'jobs/{jid}'
    sb = json.load(open(f'{d}/storyboard.json'))
    plan = json.load(open(f'{d}/plan.json'))
    T = story.build_timing(open(f'{d}/voicep_words.srt').read(), sb, plan, f'{d}/timing.json')
    if sb.get('chart') and not os.path.exists(f'{d}/data.json'):
        D, src = daily(sb['chart']['symbol'], sb['chart']['start'], sb['chart']['end'])
        if D:
            json.dump(D, open(f'{d}/data.json', 'w')); sb['chart']['src'] = src
        else:
            drop_chart(sb, 'no candles at render time')
        json.dump(sb, open(f'{d}/storyboard.json', 'w'), indent=1)
    try:                                                                  # real footage + photos (style mixed/documentary)
        import media
        got = media.fetch(d)
        print('media files:', len(got))
    except Exception as e:
        print('media skipped:', repr(e)[:150])
    env = {**os.environ, 'CS_SCALE': '1', 'FPS': '60'}
    info = json.loads(subprocess.run([sys.executable, f'{HERE}/auto.py', d, 'info'], capture_output=True, text=True, env=env, check=True).stdout.strip().split('\n')[-1])
    n, cores = info['frames'], max(2, os.cpu_count() or 2)
    step = -(-n // cores)
    procs = [subprocess.Popen([sys.executable, f'{HERE}/auto.py', d, 'part', str(a), str(min(n, a + step))], env=env) for a in range(0, n, step)]
    sh([sys.executable, f'{HERE}/auto.py', d, 'sfx'], env=env)
    for p in procs:
        if p.wait() != 0: raise SystemExit('render part failed')
    parts = sorted(glob.glob(f'{d}/part_*.mp4'))
    open(f'{d}/parts.txt', 'w').write(''.join(f"file '{os.path.basename(p)}'\n" for p in parts))
    sh(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{d}/parts.txt', '-c', 'copy', f'{d}/silent.mp4'])
    sh([sys.executable, f'{HERE}/tighten.py', f'{d}/voicep.wav', f'{d}/timing.json', f'{d}/voice_tight.wav'])
    sh(['ffmpeg', '-y', '-v', 'error', '-i', f'{HERE}/music.wav', '-i', f'{HERE}/music.wav', '-i', f'{HERE}/music.wav', '-filter_complex',
        '[0][1]acrossfade=d=2[a];[a][2]acrossfade=d=2', f'{d}/music_long.wav'])
    mv = {'serious': .08, 'mystery': .1, 'funny': .11, 'hype': .13}[sb['tone']] * {'off': 0, 'low': .55, 'normal': 1.0, 'high': 1.4}.get(story.settings(sb)['music'], 1.0)
    out = f'{d}/short.mp4'
    sh([sys.executable, f'{HERE}/mix2.py', f'{d}/silent.mp4', f'{d}/voice_tight.wav', f'{d}/sfx.wav', f'{d}/music_long.wav', str(T['dur']), out, str(mv)])
    if os.path.getsize(out) > 47e6:                                      # Telegram bots can send up to 50 MB: fit by bitrate
        kbps = int(45e6 * 8 / T['dur'] / 1000) - 256
        sh(['ffmpeg', '-y', '-v', 'error', '-i', out, '-c:v', 'libx264', '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps * 1.3)}k', '-bufsize', f'{kbps * 2}k',
            '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', f'{d}/short_s.mp4'])
        out = f'{d}/short_s.mp4'
    try:                                                                  # contact sheet of the final video (for review)
        n_ = 12
        for k in range(n_):
            sh(['ffmpeg', '-y', '-v', 'error', '-ss', f'{T["dur"] * (k + .5) / n_:.2f}', '-i', out, '-frames:v', '1', '-vf', 'scale=270:480', f'{d}/sh_{k:02d}.png'])
        sh(['ffmpeg', '-y', '-v', 'error', '-i', f'{d}/sh_%02d.png', '-vf', 'tile=6x2', '-q:v', '4', f'{d}/sheet.jpg'])
        for f in glob.glob(f'{d}/sh_*.png'): os.remove(f)
    except Exception as e:
        print('sheet skipped', e)
    hook_t = T['beats'].get('s0', 1.0)
    tg('sendVideo', {'caption': f'🎬 <b>{E(sb.get("title", ""))}</b>\n{T["dur"]:.0f}s · {sb["tone"]} · 1080p\n\n<b>Checkpoint 3:</b> watch it. Happy? Upload it. '
                                f'Want changes? Tap below.', 'supports_streaming': 'true', 'width': 1080, 'height': 1920, 'duration': int(T['dur']),
                     'reply_markup': kb([[('🔄 New voice take', f'sr:{jid}'), ('✏️ Edit script', f'se:{jid}')]])},
       files={'video': open(out, 'rb')})
    kit = (f'📦 <b>Publish kit</b>\n\n<b>Title</b>\n<code>{E(sb.get("title", ""))}</code>\n\n<b>Description</b>\n<code>{E(sb.get("description", ""))}\n\n'
           f'Not financial advice. Entertainment and education only.{E(media_credits(d))}</code>\n\n<b>Hashtags</b>\n<code>{E(sb.get("hashtags", "#crypto #bitcoin #shorts"))}</code>\n\n'
           f'<b>Pinned comment</b>\n<code>{E(sb.get("pinned", ""))}</code>\n\n<b>Cover frame</b>: {hook_t + .6:.1f}s (the big hook title)\n'
           f'<b>Post time</b>: 19:00–20:00 Beirut')
    tg('sendMessage', {'text': kit[:4000]})
    status(jid, 'done', dur=round(T['dur']), size_mb=round(os.path.getsize(out) / 1e6, 1))


if __name__ == '__main__':
    stage, jid = sys.argv[1], sys.argv[2]
    try:
        voice(jid) if stage == 'voice' else render(jid)
    except Exception as ex:
        import traceback; traceback.print_exc()
        try:
            status(jid, 'failed', stage=stage, error=repr(ex)[:200])
        except Exception:
            pass
        tg('sendMessage', {'text': f'⚠️ The {stage} step failed for this Short: <code>{E(repr(ex)[:300])}</code>\nTap to try again.',
                           'reply_markup': kb([[('🔁 Try again', f'{"sr" if stage == "voice" else "sv"}:{jid}')]])})
        raise
