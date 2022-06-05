let websocket = new WebSocket("ws://localhost:8080/ws")
let run_div

websocket.addEventListener('open', function (event) {
    console.log("Connection opened")
})

websocket.addEventListener('close', function (event) {
    console.log("Connection closed")
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
    }
})

document.getElementById('start_btn').addEventListener('click', async (event) => {
    if (![0, 1].includes(websocket.readyState)) {
        websocket = new WebSocket("ws://localhost:8080/ws")
    }

    let response = await fetch(window.location.href, {
        method: 'POST',
        body: new FormData(document.getElementById('qa_form'))
    })
    let json = await response.json()
    if ("run" in json) {
        setActive(false)

        run_header = document.createElement("h2")
        run_header.innerText = "QA execution #" + json["run"]
        debug_btn = document.createElement("a")
        debug_btn.innerText = " (show debug info)"
        debug_btn.addEventListener("click", e => showDebugInfo(e, json["run"]))
        run_header.insertAdjacentElement("beforeend", debug_btn)
        document.getElementById('runs').insertAdjacentElement('beforeend', run_header)

        run_div = document.createElement('div')
        run_div.setAttribute("class", "qa_output")
        document.getElementById('runs').insertAdjacentElement('beforeend', run_div)
    
    }
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

async function showDebugInfo(event, execution_num) {
    let debug_info = await fetch(window.location.href + "/debug/" + execution_num)
    let debug_text = await debug_info.text()
    let debug_div = document.getElementById("debug-info-" + execution_num)
    if (debug_div == null) {
        debug_div = document.createElement("div")
        debug_div.setAttribute("class", "qa_output")
        event.target.parentElement.insertAdjacentElement(afterend, debug_div)
    }
    debug_div.innerHTML = debug_text
}