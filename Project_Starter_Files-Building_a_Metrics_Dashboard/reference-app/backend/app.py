import logging
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from jaeger_client import Config
from flask_opentracing import FlaskTracing
from prometheus_flask_exporter import PrometheusMetrics
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

logging.getLogger("").handlers = []
logging.basicConfig(format="%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

app.config['MONGO_DBNAME'] = 'example-mongodb'
app.config['MONGO_URI'] = 'mongodb://192.168.178.31:27017/example-mongodb'

mongo = PyMongo(app)

metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application Info", version="1.0.3")

metrics_counter = metrics.counter(
    'by_endpoint_counter', 'Request count by endpoints',
    labels={'endpoint': lambda: request.endpoint}
)

record_requests_by_status = metrics.summary(
    'requests_by_status', 'Request latencies by status',
    labels={'status': lambda: request.status_code()}
)


def init_tracer(service):
    config = Config(
        config={
            'sampler':
                {
                    'type': 'const',
                    'param': 1
                },
            'logging': True,
            'reporter_batch_size': 1,
        },
        service_name=service,
        validate=True,
        metrics_factory=PrometheusMetricsFactory(service_name_label=service),
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()


jaeger_tracer = init_tracer("backend")
flask_tracer = FlaskTracing(jaeger_tracer, True, app)


@app.route("/")
def homepage():
    with jaeger_tracer.start_span('hello') as hello_span:
        msg = "Hello from Backend"
        hello_span.set_tag('message', msg)
    return "Hello from Backend"


@app.route("/api")
def my_api():
    with jaeger_tracer.start_span('api') as api_span:
        answer = "something"
        api_span.set_tag('message', answer)
    return jsonify(repsonse=answer)


@app.route("/star", methods=["POST"])
def add_star():
    with jaeger_tracer.start_span('star') as star_span:
        star = mongo.db.stars
        name = request.json['name']
        distance = request.json['distance']
        star_id = star.insert({'name': name, 'distance': distance})
        print(f"Star id -> {star_id}")
        output = {'name': name, 'distance': distance}
        star_span.set_tag('status', 'star')
        star_span.set_tag('name', name)
    return jsonify({'result': output})


if __name__ == "__main__":
    app.run()
