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
        result_msg.setAttribute("class", "result_msg")
        console.log(`status: <span class='${message.result}'>${message.result}</span>`)
        result_msg.insertAdjacentHTML("afterbegin", `status: <span class='${message.result}'>${message.result}</span>`)
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

document.getElementById('verbosity_fatal').addEventListener('click', e => document.getElementById('fail_at_fatal').checked = true)
document.getElementById('verbosity_error').addEventListener('click', e => {
    if (document.getElementById('fail_at_information').checked || document.getElementById('fail_at_warning').checked) {
        document.getElementById('fail_at_error').checked = true
    }
})
document.getElementById('verbosity_warning').addEventListener('click', e => {
    if (document.getElementById('fail_at_information').checked) {
        document.getElementById('fail_at_warning').checked = true
    }
})
document.getElementById('fail_at_error').addEventListener('click', e => {
    if (document.getElementById('verbosity_fatal').checked) {
        document.getElementById('verbosity_error').checked = true
    }
})
document.getElementById('fail_at_warning').addEventListener('click', e => {
    if (document.getElementById('verbosity_fatal').checked || document.getElementById('verbosity_error').checked) {
        document.getElementById('verbosity_warning').checked = true
    }
})
document.getElementById('fail_at_information').addEventListener('click', e => document.getElementById('verbosity_information').checked = true)

async function refreshFileFilter() {
    if (document.getElementById("filtered").checked) {
        // Show/enable form elements
        document.getElementById("file_name_filters").removeAttribute("disabled")
        document.getElementById("filter_result").style.display = "block"
        let waiting = document.createElement("i")
        waiting.textContent = "refreshing ..."
        document.getElementById("filter_result").replaceChildren(waiting)

        // Collect the validation steps to which the glob applies
        selected_steps = []
        document.querySelectorAll("fieldset[name='steps'] > input:checked").forEach(item => selected_steps.push(item.name.replace("step_", "")))

        // Query the server for the files that match both the steps and the file globbing 
        let json = {"files": []}
        if (document.getElementById("file_name_filters").value.trim() != "") {
            let body = new FormData()
            body.set("mode", "filtered")
            body.set("filters", document.getElementById("file_name_filters").value)
            body.set("step_names", selected_steps)
            let response = await fetch(window.location.href + "file_selection", {
                method: 'POST',
                body: body
            })
            json = await response.json()
        }

        // Display the file selection list
        let ul = document.createElement("ul")
        json["files"].forEach(file => {
            let li = document.createElement("li")
            li.textContent = file
            ul.appendChild(li)
        })
        document.getElementById("filter_result").replaceChildren(ul)
    } else {
        document.getElementById("file_name_filters").setAttribute("disabled", "disabled")
        document.getElementById("filter_result").style.display = "none"
    }
}
document.getElementsByName('check_what').forEach(node => node.addEventListener('change', refreshFileFilter))
document.getElementById("file_name_filters").addEventListener("input", refreshFileFilter)
document.querySelectorAll("fieldset[name=steps] > input[type=checkbox]").forEach(node => node.addEventListener("change", refreshFileFilter))
window.addEventListener("load", refreshFileFilter)

function setActive(is_active) {
    if (is_active) {
        document.querySelectorAll("form#qa_form > fieldset").forEach(fieldset => fieldset.removeAttribute("disabled"))
    } else {
        document.querySelectorAll("form#qa_form > fieldset").forEach(fieldset => fieldset.setAttribute("disabled", "disabled"))
    }
    
    let btn = document.getElementById('start_btn')
    btn.disabled = !is_active
    if (is_active) {
        btn.innerText = 'Perform QA'
    } else {
        btn.innerText = 'QA is running'
    }
}