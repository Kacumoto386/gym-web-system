function openEditStaff(staffId) {
    fetch('/api/staff/' + staffId)
        .then(r => r.json())
        .then(data => {
            document.getElementById('edit_name').value = data.name || '';
            document.getElementById('edit_gender').value = data.gender || '男';
            document.getElementById('edit_phone').value = data.phone || '';
            document.getElementById('edit_position').value = data.position || '';
            document.getElementById('edit_base_salary').value = data.base_salary || 0;
            document.getElementById('edit_sale_commission_rate').value = data.sale_commission_rate || 0;
            document.getElementById('edit_remark').value = data.remark || '';
            document.getElementById('editForm').setAttribute('hx-put', '/api/staff/' + staffId);
            document.getElementById('editModal').classList.remove('hidden');
        });
}
