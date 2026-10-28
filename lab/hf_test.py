# Can a free hosted GPU make a short clip? Anonymous gradio_client call to public video Spaces; reports what really happens.
import sys, time, json
try:
    from gradio_client import Client
except Exception as e:
    print('no gradio_client', e); sys.exit(0)
for space in ('Lightricks/ltx-video-distilled', 'KingNish/Instant-Video', 'multimodalart/stable-video-diffusion'):
    t0 = time.time()
    try:
        c = Client(space, verbose=False)
        api = c.view_api(print_info=False, return_format='dict')
        names = list((api.get('named_endpoints') or {}).keys())[:5]
        print(f'::notice title=hf::SPACE {space}: reachable, endpoints {names} ({time.time() - t0:.1f}s)')
    except Exception as e:
        print(f'::notice title=hf::SPACE {space}: FAILED {repr(e)[:160]}')
