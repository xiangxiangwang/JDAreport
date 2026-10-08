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
    const loadActivity = daily && selected.dataset.note === 'daily_modified_help';
    document.querySelector('.date-filter').classList.toggle('has-date-navigation', loadActivity);
    document.querySelectorAll('[data-date-step]').forEach(button => {
      button.hidden = !loadActivity;
      button.disabled = !loadActivity;
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
  const date = document.getElementById('report_date');
  const previewDate = () => {
    if (!date.disabled && report.selectedOptions[0].dataset.note === 'daily_modified_help') {
      report.form.requestSubmit(report.form.querySelector('button[value="preview"]'));
    }
  };
  document.querySelectorAll('[data-date-step]').forEach(button => {
    button.addEventListener('click', () => {
      if (!date.reportValidity()) return;
      date.valueAsNumber += Number(button.dataset.dateStep) * 86400000;
      previewDate();
    });
  });
  date.addEventListener('change', previewDate);
  updateFilters();
}
