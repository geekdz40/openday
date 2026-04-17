// Main.js - Three.js Particle Network + Form Logic for Open Day (CTF Team Auto-Grouping Model)
const CTF_MAX_PARTICIPANTS = 15;

// Three.js Particle Network (Hero Background)
let scene, camera, renderer, particles, mouse = { x: 0, y: 0 }, mouseForce = 0.1;
let linesGeometry, linesMaterial, lines;

function initThreeJS() {
    // Scene Setup
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('hero-canvas'), alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.position.z = 100;

    // Particles (Network Nodes)
    const particleCount = window.innerWidth < 768 ? 90 : 150;
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 200;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 200;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 200;
        velocities[i * 3] = (Math.random() - 0.5) * 0.02;
        velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.02;
        velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
        color: 0xEE0000,
        size: 3,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });

    particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // Lines for connections (updated in animate)
    linesGeometry = new THREE.BufferGeometry();
    linesMaterial = new THREE.LineBasicMaterial({ color: 0xEE0000, transparent: true, opacity: 0.2 });
    lines = new THREE.LineSegments(linesGeometry, linesMaterial);
    scene.add(lines);

    // Mouse listener
    document.addEventListener('mousemove', onMouseMove);
    window.addEventListener('resize', onWindowResize);

    animate();
}

function onMouseMove(event) {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);

    const positions = particles.geometry.attributes.position.array;
    const linePoints = [];

    // Update particles
    for (let i = 0; i < positions.length; i += 3) {
        // Mouse attraction/repulsion
        const dx = positions[i] - mouse.x * 50;
        const dy = positions[i + 1] - mouse.y * 50;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 50 && dist !== 0) {
            positions[i] += (dx / dist) * mouseForce * 2;
            positions[i + 1] += (dy / dist) * mouseForce * 2;
        }

        // Physics
        positions[i] += (Math.random() - 0.5) * 0.1;
        positions[i + 1] += (Math.random() - 0.5) * 0.1;
        positions[i + 2] += (Math.sin(Date.now() * 0.001 + i) * 0.01);

        // Bounds
        if (positions[i] > 100) positions[i] = -100;
        if (positions[i] < -100) positions[i] = 100;
        if (positions[i + 1] > 100) positions[i + 1] = -100;
        if (positions[i + 1] < -100) positions[i + 1] = 100;

        // Add to lines (connect nearby particles)
        for (let j = i + 3; j < positions.length; j += 3) {
            const dist = Math.sqrt(
                Math.pow(positions[i] - positions[j], 2) +
                Math.pow(positions[i + 1] - positions[j + 1], 2) +
                Math.pow(positions[i + 2] - positions[j + 2], 2)
            );
            if (dist < 30) {
                linePoints.push(
                    new THREE.Vector3(positions[i], positions[i + 1], positions[i + 2]),
                    new THREE.Vector3(positions[j], positions[j + 1], positions[j + 2])
                );
            }
        }
    }

    particles.geometry.attributes.position.needsUpdate = true;

    // Update lines
    linesGeometry.setFromPoints(linePoints);
    linesGeometry.computeBoundingSphere();

    camera.position.x += (mouse.x * 10 - camera.position.x) * 0.05;
    camera.position.y += (mouse.y * 10 - camera.position.y) * 0.05;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
}

// Form Logic
document.addEventListener('DOMContentLoaded', function() {
    const ctfCheckbox = document.getElementById('ctf-checkbox');
    const ctfLabel = document.getElementById('ctf-checkbox-label');
    const ctfStatus = document.getElementById('ctf-status');
    const soldOutBadge = document.getElementById('sold-out-badge');
    const ctfCard = document.getElementById('ctf-card');
    const ctfSoldoutSpan = document.getElementById('ctf-soldout');
    const ctfSubform = document.getElementById('ctf-subform');
    const leaderForm = document.getElementById('leader-form');
    const memberForm = document.getElementById('member-form');
    const teamSelect = document.getElementById('team_select');
    const teamNameInput = document.getElementById('team_name_input');
    const ctfRoleRadios = document.querySelectorAll('input[name="ctf_role"]');
    const registerForm = document.getElementById('register-form');
    const submitBtn = document.getElementById('submit-btn');
    const submitText = document.getElementById('submit-text');
    const submitLoading = document.getElementById('submit-loading');
    const formMessage = document.getElementById('form-message');

    // Check CTF status on load and game card clicks
    async function checkCTFStatus() {
        try {
            const response = await fetch('/ctf-count');
            const data = await response.json();
            if (data.full) {
                ctfCheckbox.disabled = true;
                ctfCheckbox.checked = false;
                ctfLabel.classList.add('opacity-50', 'cursor-not-allowed');
                ctfStatus.textContent = data.message || `تم الوصول إلى الحد الأقصى (${CTF_MAX_PARTICIPANTS}/${CTF_MAX_PARTICIPANTS})`;
                soldOutBadge.classList.remove('hidden');
                ctfCard.classList.add('opacity-50', 'cursor-not-allowed');
                ctfSoldoutSpan.classList.remove('hidden');
                ctfSubform.classList.add('hidden');
            } else {
                ctfCheckbox.disabled = false;
                ctfLabel.classList.remove('opacity-50', 'cursor-not-allowed');
                ctfStatus.textContent = data.message || `Capture the Flag - ${CTF_MAX_PARTICIPANTS} participants (5 teams x 3)`;
                soldOutBadge.classList.add('hidden');
                ctfCard.classList.remove('opacity-50', 'cursor-not-allowed');
                ctfSoldoutSpan.classList.add('hidden');
            }
        } catch (e) {
            console.error('CTF check failed:', e);
        }
    }

    async function loadAvailableTeams() {
        try {
            const response = await fetch('/available-teams');
            const teams = await response.json();
            teamSelect.innerHTML = teams.length > 0
                ? teams.map(team => `<option value="${team.name}">${team.name} (Led by ${team.leader})</option>`).join('')
                : '<option value="">No teams available</option>';
        } catch (e) {
            console.error('Failed to load teams:', e);
            teamSelect.innerHTML = '<option value="">Error loading teams</option>';
        }
    }

    checkCTFStatus();
    setInterval(checkCTFStatus, 10000);

    // CTF Checkbox Toggle Subform
    function toggleCTFSubform() {
        if (ctfCheckbox.checked && !ctfCheckbox.disabled) {
            ctfSubform.classList.remove('hidden');
            leaderForm.classList.add('hidden');
            memberForm.classList.add('hidden');
            ctfRoleRadios.forEach(r => r.checked = false);
        } else {
            ctfSubform.classList.add('hidden');
            leaderForm.classList.add('hidden');
            memberForm.classList.add('hidden');
            ctfRoleRadios.forEach(r => r.checked = false);
        }
    }
    ctfCheckbox.addEventListener('change', toggleCTFSubform);

    // CTF Role Selection
    ctfRoleRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'leader') {
                leaderForm.classList.remove('hidden');
                memberForm.classList.add('hidden');
                teamNameInput.value = '';
            } else {
                leaderForm.classList.add('hidden');
                memberForm.classList.remove('hidden');
                loadAvailableTeams();
            }
        });
    });

    // Smooth Scroll for Navbar
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // Game Cards Click to Toggle Checkbox
    document.querySelectorAll('.game-card').forEach(card => {
        card.addEventListener('click', function() {
            if (this.dataset.game === 'CTF' && ctfCheckbox.disabled) return;
            const checkbox = document.querySelector(`input[value="${this.dataset.game}"]`);
            if (!checkbox) return;
            checkbox.checked = !checkbox.checked;
            if (checkbox.id === 'ctf-checkbox') toggleCTFSubform();
        });
    });

    // Form Submit
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(registerForm);
        const games = formData.getAll('games');
        
        if (games.length === 0) {
            showMessage('Please select at least one game.', 'error');
            return;
        }
        
        if (games.includes('CTF')) {
            const ctfRole = document.querySelector('input[name="ctf_role"]:checked');
            if (!ctfRole) {
                showMessage('Please select your role (Team Leader or Team Member).', 'error');
                return;
            }
            
            formData.set('ctf_mode', 'team');
            formData.set('ctf_role', ctfRole.value);

            // Both leader input and member select share the same name, so resolve explicitly by role.
            const rawTeamName = ctfRole.value === 'leader' ? teamNameInput.value : teamSelect.value;
            const teamName = (rawTeamName || '').toString().trim();
            formData.set('team_name', teamName);

            if (!teamName) {
                showMessage(ctfRole.value === 'leader' ? 'Please enter a team name.' : 'Please select a team.', 'error');
                return;
            }
        }

        submitText.classList.add('hidden');
        submitLoading.classList.remove('hidden');

        try {
            const response = await fetch('/register', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                showMessage(data.message, 'success');
                registerForm.reset();
                ctfSubform.classList.add('hidden');
                leaderForm.classList.add('hidden');
                memberForm.classList.add('hidden');
                checkCTFStatus();
            } else {
                showMessage(data.error, 'error');
            }
        } catch (e) {
            showMessage('Submission failed. Please try again.', 'error');
        } finally {
            submitText.classList.remove('hidden');
            submitLoading.classList.add('hidden');
        }
    });

    function showMessage(msg, type) {
        formMessage.textContent = msg;
        formMessage.className = `mt-8 p-6 rounded-2xl font-semibold text-center ${type === 'success' ? 'bg-green-500/20 border-green-500/50 text-green-200 border-2' : 'bg-red-500/20 border-red-500/50 text-red-200 border-2'}`;
        formMessage.classList.remove('hidden');
    }
});

// Init
initThreeJS();
