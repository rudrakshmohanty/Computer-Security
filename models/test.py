import tensorflow as tf

model_path = r"R:\test\test2\flask-template\models\certificate_forgery_model.keras"
model = tf.keras.models.load_model(model_path)
print("Model loaded successfully!")
