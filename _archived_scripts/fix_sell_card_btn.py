"""修复 members.html 售卡按钮卡住的问题"""
with open('frontend/templates/members.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Bug 1: 成功回调中缺少 btn 恢复 + 改用 htmx.ajax 替代 htmx.trigger
old = """        htmx.trigger('#memberTable', 'load');
        setTimeout(function() {
            document.getElementById('sellCardModal').classList.add('hidden');
        }, 1500);"""

new = """        // 修复：恢复按钮状态 + 改用 htmx.ajax 刷新
        btn.disabled = false;
        btn.textContent = '💳 确认售卡';
        htmx.ajax('GET', '/api/members/table', {target: '#memberTable', swap: 'innerHTML'});
        setTimeout(function() {
            document.getElementById('sellCardModal').classList.add('hidden');
        }, 1500);"""

html = html.replace(old, new)

with open('frontend/templates/members.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("✅ members.html 售卡按钮修复完成")
