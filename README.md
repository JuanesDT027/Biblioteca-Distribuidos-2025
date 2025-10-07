# 📚 Biblioteca Distribuida – Universidad Ada Lovelace

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![ZeroMQ](https://img.shields.io/badge/Messaging-ZeroMQ-red?logo=zeromq)
![Status](https://img.shields.io/badge/Estado-En%20Desarrollo-success?style=flat-square)

## Descripción del Proyecto

Este proyecto implementa un **sistema de préstamo de libros distribuido** para estudiantes y profesores de la Universidad Ada Lovelace. El sistema permite realizar operaciones de:

- **Préstamo de libros**
- **Devolución de libros**
- **Renovación de libros**

El sistema funciona en al menos dos sedes de la biblioteca y está diseñado con **procesos distribuidos**, comunicación síncrona y asíncrona, y persistencia de datos, considerando **fallas en componentes y réplicas de base de datos**.

## Arquitectura del Sistema

El sistema consta de cuatro tipos de procesos principales:

1. **Procesos Solicitantes (PS)**  
   Generan solicitudes de operación (préstamo, devolución o renovación) ya sea desde un archivo de requerimientos o mediante un menú interactivo.

2. **Gestor de Carga (GC)**  
   Recibe solicitudes de los PS, responde de manera inmediata a las operaciones asíncronas (devolución y renovación) y coordina las operaciones de préstamo de manera síncrona con los Actores.

3. **Actores**  
   - **Actor de Préstamo**: Valida la disponibilidad de ejemplares y autoriza o deniega préstamos.  
   - **Actor de Renovación**: Actualiza las fechas de entrega de los libros renovados.  
   - **Actor de Devolución**: Registra la devolución y actualiza los ejemplares disponibles.

4. **Gestor de Almacenamiento (GA)**  
   Se encarga de persistir la información en la base de datos principal y la réplica secundaria, asegurando la consistencia y la tolerancia a fallas.

## Funcionamiento

- Las **devoluciones** y **renovaciones** son procesadas de manera **asíncrona**, usando el patrón Publicador/Suscriptor de ZeroMQ.  
- Los **préstamos** son procesados de manera **síncrona**, usando sockets REQ/REP de ZeroMQ.  
- Cada PS puede generar solicitudes desde un archivo de texto con al menos 20 requerimientos, o mediante un menú interactivo para pruebas manuales.

## Archivos y Estructura del Proyecto

- `gestor_carga/gestor_carga.py`: Procesa todas las solicitudes y publica los eventos a los Actores.
- `gestor_almacenamiento/gestor_almacenamiento.py`: Administra la base de datos principal del sistema. Atiende solicitudes de lectura y actualización de los Actores (préstamo, renovación y devolución), garantizando consistencia y persistencia de los datos.  
- `actores/actor_prestamo.py`: Atiende solicitudes de préstamo de manera síncrona.  
- `actores/actor_renovacion.py`: Atiende renovaciones publicadas por el GC.  
- `actores/actor_devolucion.py`: Atiende devoluciones publicadas por el GC.  
- `menu_interactivo.py`: Interfaz de línea de comandos para interactuar con el sistema.  
- `data/libros.txt`: Base de datos simulada de libros.  
- `common/LibroUsuario.py`: Clase que representa los libros y su estado.

## Cómo Ejecutar

1. Iniciar el **Gestor de Carga**:  
   ```bash
   python -m gestor_carga.gestor_carga
   ```  
2. Iniciar el **Gestor de Almacenamiento (GA)**:  
   ```bash
   python -m gestor_almacenamiento.gestor_almacenamiento
   ```
3. Iniciar los **Actores** (préstamo, renovación y devolución) en terminales separadas:  
   ```bash
   python -m actores.actor_prestamo
   python -m actores.actor_renovacion
   python -m actores.actor_devolucion
   ```  
4. Iniciar el **Proceso Solicitante (PS)** desde archivo o menú:  
   ```bash
   python menu_interactivo.py
   ```

## Observaciones

- Se usa **ZeroMQ** para todas las comunicaciones entre procesos.  
- Las operaciones síncronas garantizan que la información esté actualizada antes de responder al PS.  
- Se recomienda realizar pruebas con múltiples PS y observar la respuesta del sistema en tiempo real.  

## Referencias

- [ZeroMQ Guide](https://zguide.zeromq.org/)  
- [JMETER](https://jmeter.apache.org/)  
- [Locust](https://locust.io/)  
