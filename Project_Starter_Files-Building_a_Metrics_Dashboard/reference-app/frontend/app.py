from flask import Flask, render_template, request
from prometheus_flask_exporter import PrometheusMetrics
from jaeger_client import Config
from flask_opentracing import FlaskTracing
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory

app = Flask(__name__)

app.config['MONGO_DBNAME'] = 'example-mongodb'
app.config['MONGO_URI'] = 'mongodb://192.168.178.31:27017/example-mongodb'

metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application info", version="1.0.3")
common_counter = metrics.counter(
    'by_endpoint_counter', 'Request count by endpoints',
    labels={'endpoint': lambda: request.endpoint}
)
record_requests_by_status = metrics.summary(
    'requests_by_status', 'Request latencies by status',
    labels={'status': lambda: request.status_code()}
)


# -- Observability: Prep app for tracing --
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
    with jaeger_tracer.start_span("homepage") as span:
        span.set_tag('message', "homepage")
    return render_template("main.html")


@app.route("/error")
@metrics.summary(
    'requests_by_status_5xx',
    'Status Code',
    labels={'code': lambda r: '500'}
)
def error():
    return "Server Error", 500


metrics.register_default(
    metrics.counter(
        'by_path_counter', 'Request count by request paths',
        labels={'path': lambda: request.path}
    )
)


if __name__ == "__main__":
    app.run()
