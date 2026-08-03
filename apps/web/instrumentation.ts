export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { NodeTracerProvider } = await import("@opentelemetry/sdk-trace-node");
    const { OTLPTraceExporter } = await import("@opentelemetry/exporter-trace-otlp-proto");
    const { SimpleSpanProcessor } = await import("@opentelemetry/sdk-trace-base");
    const { Resource } = await import("@opentelemetry/resources");

    const provider = new NodeTracerProvider({
      resource: new Resource({
        "service.name": process.env.OTEL_SERVICE_NAME ?? "kate-web",
      }),
    });
    provider.addSpanProcessor(
      new SimpleSpanProcessor(
        new OTLPTraceExporter({
          url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://localhost:4317",
        }),
      ),
    );
    provider.register();
  }
}
