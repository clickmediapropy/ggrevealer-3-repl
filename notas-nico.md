LO QUE DEBERÍA HACER EL SISTEMA:
  1. Parsear TODAS las manos de los archivos TXT
  2. Agrupar manos por mesa (table_name)
  3. Matchear screenshots con MESAS (no con manos individuales)
  4. Extraer los nombres de los jugadores del screenshot de esa mesa
  5. Aplicar esos mappings a TODAS las manos de esa mesa

  Current Understanding (WRONG):
  - 1 screenshot → 1 hand → 1 table

  Correct Understanding (what you're describing):
  - 1 screenshot → 1 tournament → ALL tables in that tournament → ALL TXT files from that tournament

  So the logic should be:
  1. Match screenshot to a hand via Hand ID
  2. Extract Tournament ID from that hand
  3. Find ALL TXT files that share the same Tournament ID
  4. Apply the player name mappings to ALL hands in ALL those files