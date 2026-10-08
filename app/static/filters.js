const report = document.getElementById('report');
if (report) {
  const updateFilters = () => {
    const selected = report.selectedOptions[0];
    const daily = selected.dataset.kind === 'daily';
    document.querySelectorAll('.daily-filter').forEach(group => {
      group.hidden = !daily;
      group.querySelectorAll('input, select').forEach(field => {
        field.disabled = !daily;
        field.required = daily;
      });
    });
    document.getElementById('table-help').hidden = daily;
    document.getElementById('daily-help').hidden = !daily;
    document.querySelectorAll('.report-note').forEach(note => {
      note.hidden = !daily || note.dataset.note !== selected.dataset.note;
    });
    const warehouse = document.getElementById('warehouse');
    const approved = JSON.parse(selected.dataset.warehouses || '[]');
    if (daily) {
      Array.from(warehouse.options).forEach(option => {
        option.disabled = !approved.includes(option.value);
        option.hidden = option.disabled;
      });
      if (!approved.includes(warehouse.value)) warehouse.value = approved[0];
    }
  };
  report.addEventListener('change', updateFilters);
  updateFilters();
}
