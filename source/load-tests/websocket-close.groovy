import java.net.http.WebSocket
import java.util.concurrent.TimeUnit

def socket = vars.getObject('weather.socket')
def updates = vars.getObject('weather.updates')?.get() ?: 0
def invalid = vars.getObject('weather.invalid')?.get() ?: 0
def closed = vars.getObject('weather.closed')?.get() ?: 0
try {
    def valid = socket != null && updates > 0 && invalid == 0 && closed == 0
    SampleResult.setSuccessful(valid)
    SampleResult.setResponseCode(valid ? '200' : '500')
    SampleResult.setResponseMessage("updates=${updates}, invalid=${invalid}, unexpected_closes=${closed}")
    SampleResult.setResponseData(SampleResult.getResponseMessage(), 'UTF-8')
} finally {
    if (socket != null) {
        try { socket.sendClose(WebSocket.NORMAL_CLOSURE, 'done').get(5, TimeUnit.SECONDS) }
        finally { socket.abort() }
    }
}
