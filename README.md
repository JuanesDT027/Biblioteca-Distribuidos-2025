📚 Biblioteca Distribuida – Universidad Ada Lovelace
Descripción del proyecto

Este proyecto implementa un sistema de préstamo de libros distribuido para estudiantes y profesores de la Universidad Ada Lovelace. El sistema permite realizar operaciones de préstamo, devolución y renovación de libros, funcionando en al menos dos sedes de la biblioteca.

El sistema está diseñado con procesos distribuidos, comunicación síncrona y asíncrona, y persistencia de datos, considerando fallas en componentes y réplicas de base de datos.

🏗 Arquitectura

El sistema se organiza en cuatro tipos de procesos:

Procesos Solicitantes (PS):

Invocados por los usuarios para realizar operaciones sobre libros.

Pueden cargar solicitudes desde archivos o generarlas manualmente.

Se comunican síncronamente con el Gestor de Carga.

Gestor de Carga (GC):

Recibe solicitudes de los PS.

Envía tareas a los Actores según el tipo de operación.

Para devoluciones y renovaciones usa el patrón Publicador/Suscriptor (asíncrono).

Para préstamos usa comunicación síncrona con el Actor de Préstamo.

Actores:

Procesos que interactúan con la base de datos.

Se suscriben a tópicos de GC para actualizar la información de libros.

El Actor de Préstamo atiende solicitudes de manera síncrona, asegurando que el PS reciba respuesta solo cuando la operación esté completada.

Gestor de Almacenamiento (GA):

Gestiona la persistencia y réplicas de la base de datos.

Las actualizaciones en la réplica secundaria son asíncronas.

Maneja fallas en la réplica primaria de forma transparente.

⚡ Tecnologías utilizadas

Python 3.11

ZeroMQ para comunicación distribuida (REQ/REP y PUB/SUB)

JSON para intercambio de datos

Archivos de texto como base de datos simulada (data/libros.txt)

Rich para interfaz de consola interactiva

📂 Estructura del proyecto
Biblioteca-Distribuidos-2025/
│
├── actores/
│   ├── actor_prestamo.py
│   └── actor_renovacion.py
│
├── gestor_carga/
│   └── gestor_carga.py
│
├── common/
│   └── LibroUsuario.py
│
├── data/
│   └── libros.txt
│
├── menu_interactivo.py
├── solicitudes_ejemplo.txt
└── README.md

🚀 Cómo ejecutar el sistema

Preparar la base de datos

Asegúrate de que data/libros.txt contiene libros con los siguientes campos:

{
  "codigo": "L0001",
  "titulo": "Cien Años de Soledad",
  "prestado": false,
  "ejemplares_disponibles": 3,
  "fecha_entrega": null
}


Ejecutar el Gestor de Carga (GC)

python -m gestor_carga.gestor_carga


Ejecutar los Actores

Actor de Préstamo:

python -m actores.actor_prestamo


Actor de Renovación/Devolución:

python -m actores.actor_renovacion


Ejecutar el menú del PS

python menu_interactivo.py


Opciones del menú

Cargar archivo de solicitudes (.txt)

Enviar todas las solicitudes cargadas

Realizar operaciones manualmente (préstamo, devolución, renovación)

📝 Archivo de solicitudes

Ejemplo de archivo solicitudes_ejemplo.txt:

{"operacion": "devolucion", "codigo": "L0010"}
{"operacion": "renovacion", "codigo": "L0001"}
{"operacion": "prestamo", "codigo": "L0003"}
{"operacion": "prestamo", "codigo": "L0005"}


Cada línea representa una solicitud válida.

El sistema lee automáticamente cada línea y la procesa.

🛠 Pruebas y métricas

Pruebas de desempeño:

Número de solicitudes procesadas por minuto

Tiempo de respuesta promedio para préstamos

Escenarios de prueba:

Diferentes cantidades de PS distribuidos por sede

Comparación entre operaciones síncronas y asíncronas

💡 Notas importantes

La operación de préstamo es síncrona: el PS recibe la respuesta solo después de que el Actor de Préstamo confirma la disponibilidad y realiza la actualización.

Las operaciones de devolución y renovación son asíncronas: el PS recibe confirmación inmediata, mientras que los Actores actualizan la base de datos en segundo plano.

En caso de falla de la réplica primaria, el sistema cambia automáticamente a la réplica secundaria.
