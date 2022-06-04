let websocket = new WebSocket("ws://localhost:8080/ws")
let run_div

websocket.addEventListener('open', function (event) {
    console.log("Connection opened")
})

websocket.addEventListener('message', function (event) {
    console.log('Message from server ', event.data)
    run_div.insertAdjacentText('beforeend', event.data)
})

document.getElementById('start_btn').addEventListener('click', async (event) => {
    if (![0, 1].includes(websocket.readyState)) {
        websocket = new WebSocket("ws://localhost:8080/ws")
    }
    run_div = document.createElement('pre')
    document.getElementById('runs').insertAdjacentElement('beforeend', run_div)

    let response = await fetch(window.location.href, {
        method: 'POST',
        body: new FormData(document.getElementById('qa_form'))
    })
    let json = await response.json()
    console.log(json)
})
