// 绑定按钮处理：设置 PUT 请求 URL
function openBindModal(bandId) {
    document.getElementById('bindForm').setAttribute('hx-put', '/api/wristbands/' + bandId + '/bind');
    document.getElementById('bindForm').setAttribute('hx-vals', '{"member_id": ""}');
    document.getElementById('bindModal').classList.remove('hidden');
}
