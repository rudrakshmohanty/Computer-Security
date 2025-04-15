import mysql.connector
class Database:
    def __init__(self, host="localhost", user="root", password="rudraksh", database="certificate_db"):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.cursor = None
    
    def connect(self):
        """Establish a connection to the MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            return True
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return False
    
    def disconnect(self):
        """Close the database connection"""
        if self.connection:
            self.cursor.close()
            self.connection.close()
    
    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        try:
            self.cursor.execute(query, params or ())
            self.connection.commit()
            return self.cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"Query error: {err}")
            return None
