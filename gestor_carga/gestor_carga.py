import zmq

context = zmq.Context()

# Socket REP para atender Procesos Solicitantes
socket_req = context.socket(zmq.REP)
socket_req.bind("tcp://*:5555")

print("[GC] Gestor de Carga iniciado. Esperando solicitudes...")

while True:
    mensaje = socket_req.recv_json()
    operacion = mensaje.get("operacion")
    libro = mensaje.get("libro_usuario")

    print(f"[GC] Solicitud recibida: {operacion}, libro: {libro}")

    if operacion == "devolver":
        socket_req.send_json({"status": "ok", "msg": "Libro recibido"})

    elif operacion == "renovar":
        socket_req.send_json({"status": "ok", "msg": "Renovación aceptada"})

    elif operacion == "solicitar":
        socket_req.send_json({"status": "ok", "msg": "Préstamo aprobado (máx 2 semanas)"})

    else:
        socket_req.send_json({"status": "error", "msg": "Operación no reconocida"})
