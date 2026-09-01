INSERT INTO usuarios (id, nombre, email, password_hash)
VALUES (
    1,
    'Dpoloalcoba',
    'dpoloalcoba@gmail.com',
    '$2b$12$Qr.BaxrTw7O/0HklHrs62eap8D5BFqMiUbMzTHp.Q1fTtM0dM1gFO'
)
ON CONFLICT (email) DO NOTHING;

SELECT setval('usuarios_id_seq', GREATEST((SELECT MAX(id) FROM usuarios), 1), true);
