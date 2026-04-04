/**
 * Eigenform event delegation.
 *
 * Eigenforms control their own interaction by emitting data attributes.
 * This script is a thin mechanism that reads those attributes and
 * executes the fetch+swap cycle. It does not contain any eigenform
 * logic — the eigenform dictates the URL, body, and input strategy.
 *
 * Protocols:
 *   data-ef-post  + data-ef-body      — static-body click (buttons)
 *   data-ef-submit (on <form>)        — form submission, body from fields
 *   data-ef-change + data-ef-key      — checkbox: {key: checked}
 *   data-ef-change + data-ef-field    — radio/input: {field: value}
 *   data-ef-change + data-ef-template — complex: JSON with __VALUE replaced
 */

/* Static-body clicks */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-ef-post]');
    if (!el) return;
    e.preventDefault();
    _efPost(el.getAttribute('data-ef-post'), el.getAttribute('data-ef-body'));
});

/* Form submissions — body built from named form fields */
document.addEventListener('submit', function(e) {
    var form = e.target.closest('form[data-ef-submit]');
    if (!form) return;
    e.preventDefault();
    var body = {};
    new FormData(form).forEach(function(v, k) { body[k] = v; });
    _efPost(form.getAttribute('data-ef-submit'), JSON.stringify(body));
});

/* Immediate-change elements (checkbox, radio, select) */
document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-ef-change]');
    if (!el) return;
    var url = el.getAttribute('data-ef-change');
    var body;
    if (el.hasAttribute('data-ef-key')) {
        /* Checkbox: body = {key: checked} */
        body = {};
        body[el.getAttribute('data-ef-key')] = el.checked;
    } else if (el.hasAttribute('data-ef-field')) {
        /* Radio/input: body = {field: value} */
        body = {};
        body[el.getAttribute('data-ef-field')] = el.value;
    } else if (el.hasAttribute('data-ef-template')) {
        /* Template: replace __VALUE sentinel */
        body = JSON.parse(el.getAttribute('data-ef-template'));
        for (var k in body) {
            if (body[k] === '__VALUE') body[k] = el.value;
        }
    }
    if (body) _efPost(url, JSON.stringify(body));
});

function _efPost(url, body) {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/html'
        },
        body: body
    }).then(function(resp) {
        return resp.text();
    }).then(function(html) {
        var scrollY = window.scrollY;
        document.getElementById('page-content').innerHTML = html;
        window.scrollTo(0, scrollY);
    });
}
