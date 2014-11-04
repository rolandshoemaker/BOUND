import config

from flask import Flask, render_template, request, jsonify
import sys
sys.path.insert(1, '/usr/local/lib/python3.4/dist-packages/iscpy/') # guh such ghetto-hack to make this work with python 3...
import pickle, iscpy
import dns.zone
# from redis import StrictRedis

app = Flask(__name__)

def get_local_zones(confFiles):
	"""Return list of triplets containing zone name, dnspython zone object, and whether zone has changed for domains, reverses, and slaves."""
	unsaved = bool()
	for confFile in confFiles:
		with open(confFile) as input_config_file:
			conf_string = input_config_file.read()
		zones = iscpy.ParseISCString(conf_string)
		real_zones = []
		for zone_name, zone_obj in zones.items():
			if zone_name.startswith('zone '):
				zone_name = zone_name[6:-1].lower()
				if zone_obj.get('file', None) and zone_obj.get('type', None):
					zone_changed = bool()
					# check if zone name is in redis for user if so add it to real_zones instead, if not do as normal
					#try:
					real_zones.append([zone_name, dns.zone.from_file(zone_obj['file'][1:-1], zone_name), zone_obj['type'], zone_changed])
					#except:
					#	pass
	slaves = [[z[0], z[1], real_zones.pop(real_zones.index(z))][0:2] for z in real_zones if z[2].lower() == 'slave']
	reverses = [[z[0], z[1], real_zones.pop(real_zones.index(z))][0:2] for z in real_zones if z[0].lower().endswith('in-addr.arpa')]
	domains = [[z[0], z[1]] for z in real_zones[:]] # just the rest...?
	return domains, reverses, slaves, unsaved

# # Redis cache for storing changed zones until saved.
# class PickledRedis(StrictRedis):
#     def get(self, name):
#         pickled_value = super(PickledRedis, self).get(name)
#         if pickled_value is None:
#             return None
#         return pickle.loads(pickled_value)

#     def set(self, name, value, ex=None, px=None, nx=False, xx=False):
#         return super(PickledRedis, self).set(name, pickle.dumps(value), ex, px, nx, xx)

@app.route('/')
def index():
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	notifications = [] # from logs?
	return render_template('index.html', domains=domains, slaves=slaves, reverses=reverses, unsaved=unsaved, notifications=notifications)

if __name__ == '__main__':
	app.debug = True
	app.run()
