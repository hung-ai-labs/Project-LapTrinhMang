import java.net.URI
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.time.Duration
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicInteger
import groovy.json.JsonSlurper

// Each JMeter user keeps one socket while making REST requests.
def updates = new AtomicInteger()
def invalid = new AtomicInteger()
def closed = new AtomicInteger()
def buffer = new StringBuilder()
def ward = props.getProperty('ward', '00004')
def listener = new WebSocket.Listener() {
    void onOpen(WebSocket socket) { socket.request(1) }
    java.util.concurrent.CompletionStage<?> onText(WebSocket socket, CharSequence data, boolean last) {
        buffer.append(data)
        if (last) {
            try {
                def event = new JsonSlurper().parseText(buffer.toString())
                if (event.type == 'weather.update') {
                    if (event.observation.ward_id == ward && event.observation.source == 'simulator') {
                        updates.incrementAndGet()
                    } else { invalid.incrementAndGet() }
                } else if (event.type != 'heartbeat') { invalid.incrementAndGet() }
            } catch (Exception ignored) { invalid.incrementAndGet() }
            buffer.setLength(0)
        }
        socket.request(1)
        return CompletableFuture.completedFuture(null)
    }
    java.util.concurrent.CompletionStage<?> onClose(WebSocket socket, int code, String reason) {
        closed.incrementAndGet()
        return CompletableFuture.completedFuture(null)
    }
    void onError(WebSocket socket, Throwable error) { invalid.incrementAndGet() }
}
def scheme = props.getProperty('scheme', 'http') == 'https' ? 'wss' : 'ws'
def uri = new URI("${scheme}://${props.getProperty('host', '127.0.0.1')}:${props.getProperty('port', '18080')}/api/v1/ws/wards/${ward}/weather")
// Share the client across threads to avoid creating 100 client executors.
def client
synchronized (props) {
    client = props.get('weather.ws.client')
    if (client == null) {
        client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build()
        props.put('weather.ws.client', client)
    }
}
def socket = client.newWebSocketBuilder().connectTimeout(Duration.ofSeconds(10))
    .buildAsync(uri, listener).get(15, java.util.concurrent.TimeUnit.SECONDS)
vars.putObject('weather.socket', socket)
vars.putObject('weather.updates', updates)
vars.putObject('weather.invalid', invalid)
vars.putObject('weather.closed', closed)
SampleResult.setResponseCode('101')
SampleResult.setSuccessful(true)
