import zmq
import json
import threading
import os
import time
from common.LibroUsuario import LibroUsuario

ARCHIVO_PRINCIPAL = "data/libros.txt"
ARCHIVO_REPLICA = "data/libros_replica.txt"
LOCK = threading.Lock()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5560")  # GA Primario en puerto 5560

# Variable global para indicar si este GA es primario o réplica
ES_PRIMARIO = True
libros = {}

def cargar_datos():
    global libros
    libros = {}
   
    if os.path.exists(ARCHIVO_PRINCIPAL):
        try:
            with open(ARCHIVO_PRINCIPAL, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            codigo = data.get("codigo")
                            if codigo:
                                libros[codigo] = LibroUsuario(**data)
                                print(f"📚 Cargado: {codigo} - {data.get('titulo', 'Sin título')}")
                            else:
                                print(f"⚠️ Línea {line_num}: Sin código - {line[:50]}...")
                        except json.JSONDecodeError as e:
                            print(f"❌ Error JSON línea {line_num}: {e} - Contenido: {line[:50]}...")
                        except Exception as e:
                            print(f"❌ Error procesando línea {line_num}: {e}")
            
            print(f"✅ Datos cargados desde archivo principal - Total libros: {len(libros)}")
            return True
        except Exception as e:
            print(f"⚠️ Error cargando archivo principal: {e}")
   
    # Fallback a réplica si el principal falla
    if os.path.exists(ARCHIVO_REPLICA):
        try:
            with open(ARCHIVO_REPLICA, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            codigo = data.get("codigo")
                            if codigo:
                                libros[codigo] = LibroUsuario(**data)
                        except json.JSONDecodeError as e:
                            print(f"❌ Error JSON réplica línea {line_num}: {e}")
                        except Exception as e:
                            print(f"❌ Error procesando réplica línea {line_num}: {e}")
            
            print("🔄 FALLOVER ACTIVADO: Cargando datos desde réplica secundaria")
            print(f"📚 Total libros cargados desde réplica: {len(libros)}")
            print("🚨 SISTEMA CONTINÚA OPERANDO CON RÉPLICA - Failover exitoso")
            return True
        except Exception as e:
            print(f"❌ Error cargando réplica secundaria: {e}")
   
    print(f"❌ No se pudieron cargar datos - Libros en memoria: {len(libros)}")
    return False

def guardar_datos():
    """Guarda los cambios en el archivo principal y réplica."""
    with LOCK:
        try:
            # Guardar en archivo principal
            with open(ARCHIVO_PRINCIPAL, "w", encoding="utf-8") as f:
                for libro in libros.values():
                    f.write(json.dumps(libro.to_dict()) + "\n")
           
            # Replicar en archivo secundario
            with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                for libro in libros.values():
                    f.write(json.dumps(libro.to_dict()) + "\n")
                   
            print(f"💾 Datos actualizados correctamente - {len(libros)} libros guardados")
           
        except Exception as e:
            print(f"⚠️ Error guardando en archivo principal: {e}")
            print("🔄 Intentando guardar solo en réplica secundaria...")
           
            try:
                # Fallback: guardar solo en réplica
                with open(ARCHIVO_REPLICA, "w", encoding="utf-8") as f:
                    for libro in libros.values():
                        f.write(json.dumps(libro.to_dict()) + "\n")
                print(f"✅ Datos guardados en réplica secundaria - {len(libros)} libros")
            except Exception as e2:
                print(f"❌ Error crítico: No se pudo guardar en ninguna réplica: {e2}")

# Cargar datos al inicio
if cargar_datos():
    print("✅ Gestor de Almacenamiento (GA) PRIMARIO operativo en puerto 5560")
else:
    print("❌ No se pudieron cargar datos ni del archivo principal ni de la réplica")
    libros = {}

print("🚀 GA Primario iniciado en 10.43.102.150:5560 - Listo para conexiones...")
print(f"📊 Libros disponibles: {list(libros.keys())[:5]}..." if libros else "📊 Sin libros cargados")

while True:
    try:
        # Recibir mensaje
        msg = socket.recv_json()
        print(f"\n📨 MENSAJE RECIBIDO: {msg}")
        
        op = msg.get("operacion")
        codigo = msg.get("codigo")
        data = msg.get("data")

        print(f"🔍 Operación: {op}, Código solicitado: '{codigo}'")

        if op == "leer":
            if not codigo:
                error_msg = "Código no proporcionado en operación 'leer'"
                print(f"❌ {error_msg}")
                socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})
                continue
                
            libro = libros.get(codigo)
            if libro:
                respuesta = {
                    "status": "ok", 
                    "libro": libro.to_dict(), 
                    "replica": not ES_PRIMARIO
                }
                socket.send_json(respuesta)
                print(f"📖 Enviado libro {codigo} desde {'RÉPLICA' if not ES_PRIMARIO else 'PRIMARIO'}")
                print(f"📚 Detalles: {libro.titulo} - Ejemplares: {libro.ejemplares_disponibles}")
            else:
                error_msg = f"Libro '{codigo}' no encontrado"
                print(f"❌ {error_msg}")
                print(f"📋 Libros disponibles: {list(libros.keys())}")
                socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})

        elif op == "actualizar":
            if not codigo:
                error_msg = "Código no proporcionado en operación 'actualizar'"
                print(f"❌ {error_msg}")
                socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})
                continue
                
            if codigo in libros:
                print(f"🔄 Actualizando libro {codigo} con datos: {data}")
                
                # Actualizar atributos del libro
                libro_actual = libros[codigo]
                for clave, valor in data.items():
                    if hasattr(libro_actual, clave):
                        setattr(libro_actual, clave, valor)
                        print(f"   ✅ {clave} = {valor}")
                    else:
                        print(f"   ⚠️ Atributo '{clave}' no existe en LibroUsuario")
                
                # Guardar cambios
                guardar_datos()
                
                respuesta = {
                    "status": "ok", 
                    "msg": f"Libro {codigo} actualizado", 
                    "replica": not ES_PRIMARIO
                }
                socket.send_json(respuesta)
                print(f"✅ Libro {codigo} actualizado en {'RÉPLICA' if not ES_PRIMARIO else 'PRIMARIO'}")
            else:
                error_msg = f"Código '{codigo}' inexistente"
                print(f"❌ {error_msg}")
                print(f"📋 Códigos disponibles: {list(libros.keys())}")
                socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})

        elif op == "listar":
            # Operación adicional para debug - listar todos los libros
            lista_libros = {codigo: libro.to_dict() for codigo, libro in libros.items()}
            socket.send_json({"status": "ok", "libros": lista_libros, "total": len(libros), "replica": not ES_PRIMARIO})
            print(f"📋 Listado enviado - {len(libros)} libros")

        else:
            error_msg = f"Operación '{op}' no válida"
            print(f"❌ {error_msg}")
            socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})

    except json.JSONDecodeError as e:
        error_msg = f"Error decodificando JSON: {e}"
        print(f"❌ {error_msg}")
        try:
            socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})
        except:
            pass
            
    except Exception as e:
        error_msg = f"Error en GA: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        try:
            socket.send_json({"status": "error", "msg": error_msg, "replica": not ES_PRIMARIO})
        except:
            pass