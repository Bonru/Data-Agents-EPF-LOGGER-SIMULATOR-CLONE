const FB_URL = 'https://monitoramento-usf-default-rtdb.firebaseio.com/parametros.json';
const refreshInterval = 2000;

const statusElement = document.getElementById('status-text');
const timestampElement = document.getElementById('status-time');
const table = document.getElementById('data-table');
const tableBody = table.querySelector('tbody');

function formatTimestamp(date) {
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium'
  }).format(date);
}

function updateStatus(message, type = 'info') {
  statusElement.textContent = message;
  statusElement.dataset.status = type;
}

function updateTimestamp() {
  timestampElement.textContent = `Última atualização: ${formatTimestamp(new Date())}`;
}

function normalizeData(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return Object.values(value);
  return [];
}

function renderTable(items) {
  tableBody.innerHTML = '';

  if (!items.length) {
    tableBody.innerHTML = '<tr><td colspan="3" class="no-data">Nenhum parâmetro disponível no momento.</td></tr>';
    table.hidden = false;
    return;
  }

  const rows = items.map(item => {
    const name = item.name ?? item.nome ?? item.key ?? 'Sem nome';
    const value = item.value ?? item.valor ?? item.v ?? '';
    const unit = item.unit ?? item.unidade ?? item.u ?? '';

    return `<tr>
      <td>${String(name)}</td>
      <td>${String(value)}</td>
      <td>${String(unit)}</td>
    </tr>`;
  }).join('');

  tableBody.innerHTML = rows;
  table.hidden = false;
}

async function fetchParametros() {
  updateStatus('Buscando dados...');
  try {
    const response = await fetch(FB_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    const data = await response.json();
    const items = normalizeData(data);
    renderTable(items);
    updateStatus('Dados carregados com sucesso.', 'success');
    updateTimestamp();
  } catch (error) {
    renderTable([]);
    updateStatus(`Erro ao obter dados: ${error.message}`, 'error');
  }
}

fetchParametros();
setInterval(fetchParametros, refreshInterval);
