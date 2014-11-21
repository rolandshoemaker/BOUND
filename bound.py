import config

from flask import Flask, render_template, request, session, jsonify, abort, redirect, url_for, g, flash
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from passlib.apps import custom_app_context as pwd_context

import sys
sys.path.insert(1, 'lib/')
sys.path.insert(1, 'lib/iscpy/') # guh such ghetto-hack to make this work with python 3...
import pickle, iscpy, difflib, subprocess, uuid, tempfile, datetime
import dns.zone, dns.rdatatype
from redis import StrictRedis

###############
# Flask setup #
###############

app = Flask(__name__)
app.config['SECRET_KEY'] = str(uuid.uuid4())

#############
# DNS Utils #
#############

def get_local_zones(confFiles):
	"""Return list of quads containing zone name, dnspython zone object, zone type (master/slave), and whether user has changed the zone for domains, reverses, and slaves."""
	slaves = []
	reverses = []
	domains = []
	changed = predis.get(current_user.name+":zones")
	if changed:
		return changed['domains'], changed['reverses'], changed['slaves'], True
	for confFile in confFiles:
		with open(confFile) as input_config_file:
			conf_string = input_config_file.read()
		zones = iscpy.ParseISCString(conf_string)
		real_zones = []
		for zone_name, zone_obj in zones.items():
			if zone_name.startswith('zone '):
				zone_name = zone_name[6:-1].lower()
				if zone_obj.get('file', None) and zone_obj.get('type', None):
					zone = None
					try:
						zone = dns.zone.from_file(zone_obj['file'][1:-1], zone_name, relativize=config.relativize_zones)
					# should do something with these eventually
					except BadZone:
						pass
					except NoSOA:
						pass
					except NoNS:
						pass
					except UnknownOrigin:
						pass
					if zone_obj['type'].lower() == 'slave':
						masters = list(zone_obj.get('masters', None))
						masters.reverse()
						slaves.append([zone_name, zone, zone_obj['type'], False, True, masters])
					else:
						real_zones.append([zone_name, zone, zone_obj['type'], False])
				elif zone_obj['type'].lower() == 'slave' and zone_obj.get('masters', None):
					masters = list(zone_obj['masters'])
					masters.reverse()
					slaves.append([zone_name, None, zone_obj['type'], False, False, masters])

	for z in real_zones:
		if z[0].lower().endswith('in-addr.arpa'):
			reverses.append(z)
		else:
			domains.append(z)

	return domains, reverses, slaves, False

def zone_to_text(zone):
	after_tmp = tempfile.TemporaryFile(mode='w+t')
	zone.to_file(after_tmp, sorted=config.dnssec_order, relativize=config.relativize_zones)
	after_tmp.seek(0)
	after = after_tmp.read()
	after_tmp.close()
	return after

def zone_file_diff(before_path, after_obj):
	bfile = open(before_path, 'r')
	before = bfile.read()
	bfile.close()
	after = zone_to_text(after_obj)
	return difflib.unified_diff(before.split("\n"), after.split("\n"))

def get_bind_stats():
	proc = subprocess.Popen(['bash', config.check_bind_bin]+config.check_bind_xtra, stdout=subprocess.PIPE)
	tmp = proc.stdout.read().decode('utf-8').replace('\\n', '').replace('"', '')
	running = bool()
	if tmp.startswith('Bind9 is running'):
		rrd = tmp.split(' | ')[1].split(' ')
		stuff = {}
		for r in rrd:
			stuff[r.split('=')[0][1:-1]] = int(r.split('=')[1])
		stuff['running'] = True
		return stuff
	else:
		return {'running': False}


###############
# Redis Utils #
###############

class PickledRedis(StrictRedis):
    def get(self, name):
        pickled_value = super(PickledRedis, self).get(name)
        if pickled_value is None:
            return None
        return pickle.loads(pickled_value)

    def set(self, name, value, ex=None, px=None, nx=False, xx=False):
        return super(PickledRedis, self).set(name, pickle.dumps(value), ex, px, nx, xx)

predis = PickledRedis()

##############
# Auth stuff #
##############

app.config['SQLALCHEMY_DATABASE_URI'] = config.user_token_store
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))

    def __init__(self, name):
    	self.name = name

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def is_authenticated(self):
    	return True

    def is_active(self):
    	return True

    def is_anonymous(self):
    	return False

    def get_id(self):
    	return str(self.id) # python 3 unicoding yo

    def __repr__(self):
    	return '<User %r>' % (self.name)

login_manager = LoginManager()
login_manager.init_app(app)

@app.before_request
def before_request():
    g.user = current_user

@login_manager.user_loader
def load_user(userid):
    return User.query.get(int(userid))

@app.route('/login', methods=['POST', 'GET'])
def login_view():
	if g.user is not None and g.user.is_authenticated():
		return redirect(url_for('index'))
	if request.method == 'GET':
		return render_template('login.html')
	elif request.method == 'POST':
		if request.form['username'] and request.form['password']:
			user = User.query.filter_by(name=request.form['username']).first()
			if user and user.verify_password(request.form['password']):
				login_user(user)
				return redirect(request.form.get('next') or url_for('index'))
			else:
				return unauthorized()
		else:
			return unauthorized()

@app.route('/logout')
@login_required
def logout():
	logout_user()
	return redirect(url_for('login_view'))

@login_manager.unauthorized_handler
def unauthorized():
	if 'username' in request.form or 'password' in request.form:
		flash('Bad credentials, please try again.')
	else:
		flash('Login required.')
	return redirect(url_for('login_view')) 

####################
# Front end routes #
####################

@app.route('/')
@login_required
def index():
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	notifications = [] # from logs?
	return render_template('dashboard.html', domains=domains, slaves=slaves, reverses=reverses, unsaved=unsaved, notifications=notifications, page='dashboard')

@app.route('/domain/<string:domain_name>', methods=['GET'])
@app.route('/reverse/<string:reverse_name>', methods=['GET'])
@app.route('/slave/<string:slave_name>', methods=['GET'])
@login_required
def get_records(domain_name=None, reverse_name=None, slave_name=None):
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	notifications = [] # from logs?
	inspect_thing = None
	zone_type = None
	if domain_name:
		for d in domains:
			if d[0] == domain_name:
				page = 'zone/domain/'+domain_name
				inspect_thing = d
				zone_type = 'domain'
	elif reverse_name:
		for r in reverses:
			if r[0] == reverse_name:
				page = 'zone/reverse/'+reverse_name
				inspect_thing = r
				zone_type = 'reverse'
	elif slave_name:
		for s in slaves:
			if s[0] == slave_name and s[5]:
				page = 'zone/slaves'
				inspect_thing = s
				zone_type = 'slave'
	else:
		flash('Invalid request, zone name is required.')
		return redirect(url_for('index'))

	if inspect_thing:
		return render_template('zone.html', inspect_zone=inspect_thing, domains=domains, reverses=reverses, unsaved=unsaved, notifications=notifications, rtype_to_text=dns.rdatatype.to_text, str=str, len=len, page=page, z2t=zone_to_text(inspect_thing[1]), now=str(datetime.datetime.utcnow())+' UTC', zone_type=zone_type)
	else:
		flash('Invalid request, zone name/zone is bad.')
		return redirect(url_for('index'))

@app.route('/slaves', methods=['GET'])
@login_required
def slaves():
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	return render_template('slaves.html', domains=domains, reverses=reverses, slaves=slaves, page='zone/slaves')

@app.route('/new_zone/<string:zone_type>', methods=['GET'])
@login_required
def new_zone(zone_type):
	if zone_type in ['domain', 'reverse']:
		domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
		return render_template('new_zone.html', zone_type=zone_type, page='zone/'+zone_type+'/new', domains=domains, reverses=reverses, unsaved=unsaved)
	else:
		flash('Invalid zone type \''+zone_type+'\'.')
		return redirect(url_for('index'))

##############
# API routes #
##############

@app.route('/api/v1/bind_stats', methods=['GET'])
@login_required
def stats_endpoint():
	"""Return current BIND stats."""
	return jsonify(get_bind_stats())

@app.route('/api/v1/bind_running', methods=['GET'])
@login_required
def running_endpoint():
	"""Return wether BIND is running."""
	return jsonify({'running': get_bind_stats()['running']})

@app.route('/api/v1/users', methods=['POST', 'UPDATE', 'DELETE'])
def api_user():
	pass

@app.route('/api/v1/zone', methods=['POST', 'UPDATE', 'DELETE'])
def api_zone():
	pass

@app.route('/api/v1/record', methods=['POST', 'UPDATE', 'DELETE'])
def api_record():
	pass

#############
# Dev stuff #
#############

if __name__ == '__main__':
	# Build DB and add admin user with default password from config.default_admin_password
	db.create_all()
	db.session.commit()
	admin = User(name='admin')
	admin.hash_password(config.default_admin_password)
	db.session.add(admin)
	db.session.commit()
	app.debug = True
	app.run(host=config.host, port=config.port)
