from flask import Flask, render_template, request, jsonify
import pickle
# from redis import StrictRedis

app = Flask(__name__)

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
	unsaved = bool # stuff in cache for person?
	domains = []  # get local + check if they were updated
	slaves = []   #  ^ 
	reverses = [] #  |

	notifications = [] # from logs?
	return render_template('index.html', domains=domains, slaves=slaves, reverses=reverses, unsaved=unsaved, notifications=notifications)

if __name__ == '__main__':
	app.debug = True
	app.run()
