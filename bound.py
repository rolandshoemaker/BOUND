import config

from flask import Flask, render_template, request, session, jsonify, abort, redirect, url_for, g, flash
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_user, logout_user, current_user, login_required

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from passlib.apps import custom_app_context as pwd_context

import sys
sys.path.insert(1, 'lib/')
sys.path.insert(1, 'lib/iscpy/') # guh such ghetto-hack to make this work with python 3...
import pickle, iscpy, difflib, subprocess, uuid
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
					zone = None
					zone_changed = bool()
					# check if zone name is in redis for user if so add it to real_zones instead, if not do as normal
					changed = predis.get(g.user.name+zone_name)
					if changed:
						zone = changed
						zone_changed = True
						unsaved = True
					else:
						try:
							zone = dns.zone.from_file(zone_obj['file'][1:-1], zone_name)
						except:
							# do something
							pass
					if zone:
						real_zones.append([zone_name, zone, zone_obj['type'], zone_changed])
	slaves = []
	reverses = []
	domains = []
	for z in real_zones:
		if z[2].lower() == 'slave':
			slaves.append(z)
		elif z[0].lower().endswith('in-addr.arpa'):
			reverses.append(z)
		else:
			domains.append(z)
	return domains, reverses, slaves, unsaved

def unrelativize(zone_name, name):
	# make this a toggle option in settings?
	if str(name) == "@":
		return zone_name+'.'
	else:
		return str(name)+'.'+zone_name+'.'

def zone_file_diff(before_path, after_obj):
	bfile = open(before_path, 'r')
	before = bfile.read()
	bfile.close()
	after_tmp = tempfile.TemporaryFile(mode='w+t')
	after_obj.to_file(after_tmp)
	after.seek(0)
	after = after.read()
	after_tmp.close()
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
				remember_me = False
				if 'remember_me' in request.form:
					remember_me = request.form['remember_me']
				login_user(user, remember=remember_me)
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

@app.route('/domain/<string:domain_name>')
@app.route('/reverse/<string:reverse_name>')
@login_required
def get_records(domain_name=None, reverse_name=None):
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	notifications = [] # from logs?
	inspect_thing = None
	if domain_name:
		for d in domains:
			if d[0] == domain_name:
				page = 'zone/domain/'+domain_name
				inspect_thing = d
	elif reverse_name:
		for r in reverses:
			if r[0] == reverse_name:
				page = 'zone/reverse/'+reverse_name
				inspect_thing = r
	else:
		flash('Invalid request, zone name is required.')
		return redirect(url_for('index'))

	if inspect_thing:
		return render_template('zone.html', inspect_zone=inspect_thing, domains=domains, reverses=reverses, unsaved=unsaved, notifications=notifications, rtype_to_text=dns.rdatatype.to_text, unrelativize=unrelativize, str=str, len=len, page=page)
	else:
		flash('Invalid request, zone name/zone is bad.')
		return redirect(url_for('index'))

@app.route('/slaves', methods=['GET'])
@login_required
def slaves():
	domains, reverses, slaves, unsaved = get_local_zones(config.bind_zone_confs)
	return render_template('slaves.html', slaves=slaves, page='zone/slaves')

@app.route('/new_zone/<string:zone_type>', methods=['GET'])
@login_required
def new_zone(zone_type):
	if zone_type in ['domain', 'reverse']:
		return render_template('new_zone.html', zone_type=zone_type, page='zone/'+zone_type+'/new')
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
