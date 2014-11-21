from bind_stats_parser import BindStatsParser
import config

import threading, datetime, pickle
from subprocess import call
from redis import StrictRedis

class PickledRedis(StrictRedis):
    def get(self, name):
        pickled_value = super(PickledRedis, self).get(name)
        if pickled_value is None:
            return None
        return pickle.loads(pickled_value)

    def set(self, name, value, ex=None, px=None, nx=False, xx=False):
        return super(PickledRedis, self).set(name, pickle.dumps(value), ex, px, nx, xx)

predis = PickledRedis(host='localhost', port=6379)

parser = BindStatsParser(config.bind_stats_path)

def strip_stats(stats):
	success = 0
	referral = 0
	nxrrset = 0
	nxdomain = 0
	recursion = 0
	failure = 0
	duplicate = 0
	for line in stats:
		if line[4].endswith('resulted in successful answer'):
			success += int(line[3])
		elif line[4].endswith('resulted in referral'):
			referral += int(line[3])
		elif line[4].endswith('resulted in nxrrset'):
			nxrrset += int(line[3])
		elif line[4].endswith('resulted in NXDOMAIN'):
			nxdomain += int(line[3])
		elif line[4].endswith('caused recursion'):
			recursion += int(line[3])
		elif line[4].endswith('resulted in SERVFAIL'):
			failure += int(line[3])
		elif line[4].endswith('duplicate queries received'):
			duplicate += int(line[3])
	return {'successes': success, 'referrals': referral, 'nxrrset': nxrrset, 'nxdomain': nxdomain, 'recursions': recursion, 'failures': failure, 'duplicates': duplicate}

def stats_loop():
	if config.generate_stats:
		threading.Timer(config.bind_stats_interval, stats_loop).start()
		pre_stats = strip_stats(parser.Parse())
		call(['rndc', 'stats'])
		post_stats = strip_stats(parser.Parse())
		now = datetime.datetime.now()
		all_stats = predis.get('bind_stats')
		if not all_stats:
			all_stats = {'successes': [], 'referrals': [], 'nxrrset': [], 'nxdomain': [], 'recursions': [], 'failures': [], 'duplicates': [], 'length': 0}
		if all_stats['length'] == config.bind_stats_range:
			all_stats['successes'].pop(0)
			all_stats['referrals'].pop(0)
			all_stats['nxrrset'].pop(0)
			all_stats['nxdomain'].pop(0)
			all_stats['recursions'].pop(0)
			all_stats['failures'].pop(0)
			all_stats['duplicates'].pop(0)
			all_stats['length'] -= 1
		all_stats['successes'].append([now, post_stats['successes']-pre_stats['successes']])
		all_stats['referrals'].append([now, post_stats['referrals']-pre_stats['referrals']])
		all_stats['nxrrset'].append([now, post_stats['nxrrset']-pre_stats['nxrrset']])
		all_stats['nxdomain'].append([now, post_stats['nxdomain']-pre_stats['nxdomain']])
		all_stats['recursions'].append([now, post_stats['recursions']-pre_stats['recursions']])
		all_stats['failures'].append([now, post_stats['failures']-pre_stats['failures']])
		all_stats['duplicates'].append([now, post_stats['duplicates']-pre_stats['duplicates']])
		all_stats['length'] += 1
		predis.set('bind_stats', all_stats)
	else:
		return 0