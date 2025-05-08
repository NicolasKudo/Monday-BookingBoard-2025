--------------------------------------------------------------------------------------------------------------------------------------------------------\

VARIABLES DE ENTORNO:

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY","eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjMyOTEwMjE3NiwiYWFpIjoxMSwidWlkIjoyNTgzODY5NCwiaWFkIjoiMjAyNC0wMy0wNVQyMDowNDo1Mi4zNzJaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTAwMjkxMDQsInJnbiI6InVzZTEifQ.4FXViuW0ZIOUBuCBt3DVBKwtaj3B9wrO3tgO7mrpjTk")
BOOKING_BOARD_ID = os.getenv("BOOKING_BOARD_NUMBER",8883743273)
SUB_BOOKING_BOARD_ID = os.getenv("SUB_BOOKING_BOARD_ID","group_title")
BUCKET_NAME = os.getenv("BUCKET_NAME","monday-booking-boards")
STORED_VARIABLES_SUB_FOLDER = os.getenv("STORED_VARIABLES_SUB_FOLDER","stored_variables")
OUTPUT_FILE_NAME = os.getenv("OUTPUT_FILE_NAME","bookings_ps_df_2025")
OUTPUT_FILE_NAME_LAST_UPDATE = os.getenv("OUTPUT_FILE_NAME","bookings_ps_items_last_update_stored_2025")

--------------------------------------------------------------------------------------------------------------------------------------------------------

Cuidado APP Docker en AWS con M1/…. al crear la imagen luego de clonar el repository de github en la compu local se tiene que hacer asi:

docker buildx create --use
docker buildx build --platform linux/amd64 -t monday-bookingboard-app . --load

especificamndo que sea linux/amd64 sino no funciona

y despues push con

docker tag monday-bookingboard-app:latest 352724981691.dkr.ecr.us-east-1.amazonaws.com/monday-bookingboard-app:latest
docker push 352724981691.dkr.ecr.us-east-1.amazonaws.com/monday-bookingboard-app:latest
