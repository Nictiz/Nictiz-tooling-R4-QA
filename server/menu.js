let websocket = new WebSocket("ws://localhost:9000/ws")
let run_div

websocket.addEventListener('open', function (event) {
    console.log("Connection opened")
})

websocket.addEventListener('message', function (event) {
    message = JSON.parse(event.data)
    if ("output" in message) {
        run_div.insertAdjacentHTML('beforeend', message.output)
        run_div.scrollTop = run_div.scrollHeight
    } else if ("result" in message) {
        setActive(true)
        let result_msg = document.createElement('p')
        result_msg.innerText = message["result"]
        document.getElementById('runs').insertAdjacentElement("beforeend", result_msg)
    } else if ("status" in message && message["status"] == "running") {
        setActive(false)
    }
})

document.getElementById('start_btn').addEventListener('click', async (event) => {
    if (![0, 1].includes(websocket.readyState)) {
        websocket = new WebSocket("ws://localhost:9000/ws")
    }
    run_div = document.createElement('div')
    run_div.setAttribute("class", "qa_output")
    document.getElementById('runs').insertAdjacentElement('beforeend', run_div)

    let response = await fetch(window.location.href, {
        method: 'POST',
        body: new FormData(document.getElementById('qa_form'))
    })
})

function setActive(is_active) {
    let btn = document.getElementById('start_btn')
    btn.disabled = !is_active
    if (is_active) {
        btn.innerText = 'Perform QA'
    } else {
        btn.innerText = 'QA is running'
    }
}