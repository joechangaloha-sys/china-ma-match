const priority = document.getElementById('priority');
const selection = document.getElementById('selection');

function updateProfile() {
  selection.textContent = priority.value;
}

priority.addEventListener('change', updateProfile);
updateProfile();
