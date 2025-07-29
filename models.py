from app import db
from datetime import datetime
from werkzeug.security import check_password_hash
import logging

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reservations = db.relationship('Reservation', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Price per hour
    address = db.Column(db.Text, nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    maximum_number_of_spots = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    parking_spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade='all, delete-orphan')
    
    def get_available_spots_count(self):
        return ParkingSpot.query.filter_by(lot_id=self.id, status='A').count()
    
    def get_occupied_spots_count(self):
        return ParkingSpot.query.filter_by(lot_id=self.id, status='O').count()
    
    def __repr__(self):
        return f'<ParkingLot {self.prime_location_name}>'

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')  # 'A' for Available, 'O' for Occupied
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reservations = db.relationship('Reservation', backref='parking_spot', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ParkingSpot {self.spot_number} - {self.status}>'

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    parking_cost = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def calculate_cost(self):
        """Calculate the cost of parking based on duration and lot price"""
        try:
            logging.debug(f"Starting cost calculation for reservation {self.id}")
            logging.debug(f"  leaving_timestamp: {self.leaving_timestamp}")
            logging.debug(f"  parking_timestamp: {self.parking_timestamp}")
            
            if not self.leaving_timestamp:
                logging.debug("  No leaving timestamp - returning 0")
                return 0.0
            
            if not hasattr(self, 'parking_spot') or not self.parking_spot:
                logging.debug("  No parking_spot relationship - returning 0")
                return 0.0
                
            if not hasattr(self.parking_spot, 'parking_lot') or not self.parking_spot.parking_lot:
                logging.debug("  No parking_lot relationship - returning 0")
                return 0.0
            
            # Calculate duration in hours
            duration = self.leaving_timestamp - self.parking_timestamp
            hours = duration.total_seconds() / 3600
            
            logging.debug(f"  Raw duration: {duration}")
            logging.debug(f"  Hours calculated: {hours}")
            
            # Minimum 1 hour charge - this is the key requirement!
            hours = max(1.0, hours)  # Ensure at least 1 hour is charged
            
            # Get the price per hour from the parking lot
            price_per_hour = float(self.parking_spot.parking_lot.price)
            
            # Calculate total cost
            total_cost = round(hours * price_per_hour, 2)
            
            logging.debug(f"Cost calculation for reservation {self.id}:")
            logging.debug(f"  Final hours (min 1hr): {hours:.2f} hours")
            logging.debug(f"  Price per hour: ₹{price_per_hour}")
            logging.debug(f"  Calculation: {hours} * {price_per_hour} = {total_cost}")
            logging.debug(f"  Final total cost: ₹{total_cost}")
            
            return total_cost
                
        except Exception as e:
            logging.error(f"Error calculating cost for reservation {self.id}: {str(e)}")
            logging.error(f"  Exception type: {type(e).__name__}")
            import traceback
            logging.error(f"  Traceback: {traceback.format_exc()}")
            
        return 0.0
    
    def get_duration_text(self):
        if self.leaving_timestamp:
            duration = self.leaving_timestamp - self.parking_timestamp
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            duration = datetime.utcnow() - self.parking_timestamp
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m (ongoing)"
    
    def __repr__(self):
        return f'<Reservation {self.id} - Spot {self.spot_id}>'
