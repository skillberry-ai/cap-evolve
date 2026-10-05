import json
d = json.load(open('/tmp/splits.json'))
print('VAL tasks (%d):' % len(d['val']))
for t in d['val']:
    print(' ', t)
print('N train:', len(d.get('train', [])))
