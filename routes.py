from flask import render_template, request, redirect, url_for, flash, session, jsonify
from app import app, db
from models import User, ParkingLot, ParkingSpot, Reservation
from forms import LoginForm, RegisterForm, ParkingLotForm
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from utils import login_required, admin_required
import logging

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            
            if user.is_admin():
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = ParkingSpot.query.filter_by(status='A').count()
    total_users = User.query.filter_by(role='user').count()
    active_reservations = Reservation.query.filter_by(status='active').count()
    
    # Get recent parking lots
    recent_lots = ParkingLot.query.order_by(ParkingLot.created_at.desc()).limit(5).all()
    
    # Get parking lot statistics for charts
    lots_data = []
    for lot in ParkingLot.query.all():
        lots_data.append({
            'name': lot.prime_location_name,
            'total': lot.maximum_number_of_spots,
            'occupied': lot.get_occupied_spots_count(),
            'available': lot.get_available_spots_count()
        })
    
    # Calculate total revenue from completed reservations
    completed_reservations = Reservation.query.filter_by(status='completed').all()
    total_revenue = sum([r.parking_cost or 0 for r in completed_reservations])
    
    return render_template('admin_dashboard.html',
                         total_lots=total_lots,
                         total_spots=total_spots,
                         occupied_spots=occupied_spots,
                         available_spots=available_spots,
                         total_users=total_users,
                         active_reservations=active_reservations,
                         recent_lots=recent_lots,
                         lots_data=lots_data,
                         total_revenue=total_revenue)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    user_id = session.get('user_id')
    
    # Get user's active reservations
    active_reservations = Reservation.query.filter_by(user_id=user_id, status='active').all()
    
    # Get user's completed reservations
    completed_reservations = Reservation.query.filter_by(user_id=user_id, status='completed').order_by(Reservation.leaving_timestamp.desc()).limit(5).all()
    
    # Calculate total spent
    total_spent = sum([r.parking_cost or 0 for r in completed_reservations])
    
    # Get available parking lots
    available_lots = []
    for lot in ParkingLot.query.all():
        if lot.get_available_spots_count() > 0:
            available_lots.append(lot)
    
    return render_template('user_dashboard.html',
                         active_reservations=active_reservations,
                         completed_reservations=completed_reservations,
                         total_spent=total_spent,
                         available_lots=available_lots)

@app.route('/admin/parking-lots')
@admin_required
def parking_lots():
    lots = ParkingLot.query.all()
    return render_template('parking_lots.html', lots=lots)

@app.route('/admin/create-parking-lot', methods=['GET', 'POST'])
@admin_required
def create_parking_lot():
    form = ParkingLotForm()
    if form.validate_on_submit():
        lot = ParkingLot(
            prime_location_name=form.prime_location_name.data,
            price=form.price.data,
            address=form.address.data,
            pin_code=form.pin_code.data,
            maximum_number_of_spots=form.maximum_number_of_spots.data
        )
        db.session.add(lot)
        db.session.flush()  # To get the lot ID
        
        # Create parking spots
        for i in range(1, form.maximum_number_of_spots.data + 1):
            spot = ParkingSpot(
                lot_id=lot.id,
                spot_number=f"S{i:03d}",
                status='A'
            )
            db.session.add(spot)
        
        db.session.commit()
        flash('Parking lot created successfully!', 'success')
        return redirect(url_for('parking_lots'))
    
    return render_template('create_parking_lot.html', form=form)

@app.route('/admin/edit-parking-lot/<int:lot_id>', methods=['GET', 'POST'])
@admin_required
def edit_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    form = ParkingLotForm(obj=lot)
    
    if form.validate_on_submit():
        current_spots = lot.maximum_number_of_spots
        new_spots = form.maximum_number_of_spots.data
        
        lot.prime_location_name = form.prime_location_name.data
        lot.price = form.price.data
        lot.address = form.address.data
        lot.pin_code = form.pin_code.data
        lot.maximum_number_of_spots = new_spots
        
        # Adjust parking spots if needed
        if new_spots > current_spots:
            # Add new spots
            for i in range(current_spots + 1, new_spots + 1):
                spot = ParkingSpot(
                    lot_id=lot.id,
                    spot_number=f"S{i:03d}",
                    status='A'
                )
                db.session.add(spot)
        elif new_spots < current_spots:
            # Check if we can remove spots (only if they're available)
            spots_to_remove = ParkingSpot.query.filter_by(lot_id=lot.id).filter(
                ParkingSpot.spot_number.like(f"S{new_spots + 1:03d}%")
            ).all()
            
            occupied_spots_to_remove = [s for s in spots_to_remove if s.status == 'O']
            if occupied_spots_to_remove:
                flash('Cannot reduce spots: Some spots are currently occupied', 'error')
                return render_template('edit_parking_lot.html', form=form, lot=lot)
            
            # Remove available spots
            for spot in spots_to_remove:
                if spot.spot_number > f"S{new_spots:03d}":
                    db.session.delete(spot)
        
        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('parking_lots'))
    
    return render_template('edit_parking_lot.html', form=form, lot=lot)

@app.route('/admin/delete-parking-lot/<int:lot_id>')
@admin_required
def delete_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if all spots are available
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot: Some spots are currently occupied', 'error')
        return redirect(url_for('parking_lots'))
    
    db.session.delete(lot)
    db.session.commit()
    flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('parking_lots'))

@app.route('/book-parking/<int:lot_id>')
@login_required
def book_parking(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if user already has an active reservation
    user_id = session.get('user_id')
    active_reservation = Reservation.query.filter_by(user_id=user_id, status='active').first()
    if active_reservation:
        flash('You already have an active parking reservation', 'error')
        return redirect(url_for('user_dashboard'))
    
    # Find first available spot
    available_spot = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').first()
    if not available_spot:
        flash('No available spots in this parking lot', 'error')
        return redirect(url_for('user_dashboard'))
    
    # Create reservation
    reservation = Reservation(
        spot_id=available_spot.id,
        user_id=user_id,
        parking_timestamp=datetime.utcnow(),
        status='active'
    )
    
    # Update spot status
    available_spot.status = 'O'
    
    db.session.add(reservation)
    db.session.commit()
    
    flash(f'Parking spot {available_spot.spot_number} booked successfully!', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/release-parking/<int:reservation_id>')
@login_required
def release_parking(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    user_id = session.get('user_id')
    
    # Check if this reservation belongs to the current user
    if reservation.user_id != user_id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('user_dashboard'))
    
    if reservation.status != 'active':
        flash('This reservation is not active', 'error')
        return redirect(url_for('user_dashboard'))
    
    try:
        # Set leaving timestamp
        reservation.leaving_timestamp = datetime.utcnow()
        
        # Reload the reservation with all relationships using joinedload
        from sqlalchemy.orm import joinedload
        reservation_with_relations = db.session.query(Reservation).options(
            joinedload(Reservation.parking_spot).joinedload(ParkingSpot.parking_lot)
        ).filter_by(id=reservation.id).first()
        
        # Update the leaving timestamp on the reloaded reservation
        reservation_with_relations.leaving_timestamp = reservation.leaving_timestamp
        
        # Double-check that we have the reservation
        if not reservation_with_relations:
            flash('Reservation not found', 'error')
            return redirect(url_for('user_dashboard'))
        
        parking_spot = reservation_with_relations.parking_spot
        parking_lot = parking_spot.parking_lot
        
        logging.debug(f"Releasing parking for reservation {reservation_with_relations.id}")
        logging.debug(f"Parking spot: {parking_spot.spot_number}")
        logging.debug(f"Parking lot: {parking_lot.prime_location_name}")
        logging.debug(f"Price per hour: ₹{parking_lot.price}")
        logging.debug(f"Parking timestamp: {reservation_with_relations.parking_timestamp}")
        logging.debug(f"Leaving timestamp: {reservation_with_relations.leaving_timestamp}")
        
        # Calculate cost with loaded relationships
        calculated_cost = reservation_with_relations.calculate_cost()
        
        # GUARANTEED cost calculation - always at least 1 hour minimum
        duration = reservation_with_relations.leaving_timestamp - reservation_with_relations.parking_timestamp
        duration_hours = duration.total_seconds() / 3600
        
        # MINIMUM 1 HOUR CHARGE - this is the key requirement
        billing_hours = max(1.0, duration_hours)  
        price_per_hour = float(parking_lot.price)
        calculated_cost = round(billing_hours * price_per_hour, 2)
        
        logging.debug(f"GUARANTEED COST CALCULATION:")
        logging.debug(f"  Duration: {duration}")
        logging.debug(f"  Duration in hours: {duration_hours:.4f}")
        logging.debug(f"  Billing hours (min 1.0): {billing_hours:.4f}")
        logging.debug(f"  Price per hour: ₹{price_per_hour}")
        logging.debug(f"  Final cost: {billing_hours:.4f} * {price_per_hour} = ₹{calculated_cost}")
        
        # Ensure cost is never 0 or negative
        if calculated_cost <= 0:
            calculated_cost = price_per_hour  # Force at least 1 hour cost
            logging.warning(f"Cost was ≤0, forcing to minimum 1 hour: ₹{calculated_cost}")
        
        # Update the original reservation object
        reservation = reservation_with_relations
        
        reservation.parking_cost = calculated_cost
        reservation.status = 'completed'
        
        # Update spot status
        parking_spot.status = 'A'
        
        # Commit all changes
        db.session.commit()
        
        logging.debug(f"Successfully calculated and saved cost: ₹{calculated_cost}")
        
        flash(f'Parking released successfully! Total cost: ₹{calculated_cost:.2f}', 'success')
        
    except Exception as e:
        logging.error(f"Error releasing parking for reservation {reservation_id}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        db.session.rollback()
        flash('An error occurred while releasing parking. Please try again.', 'error')
    
    return redirect(url_for('user_dashboard'))

@app.route('/my-bookings')
@login_required
def my_bookings():
    user_id = session.get('user_id')
    reservations = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.created_at.desc()).all()
    return render_template('my_bookings.html', reservations=reservations)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.filter_by(role='user').all()
    active_users = [u for u in users if any(r.status == 'active' for r in u.reservations)]
    return render_template('admin_users.html', users=users, active_users_count=len(active_users))

# API endpoints for charts
@app.route('/api/parking-stats')
@admin_required
def parking_stats_api():
    lots_data = []
    for lot in ParkingLot.query.all():
        lots_data.append({
            'name': lot.prime_location_name,
            'total': lot.maximum_number_of_spots,
            'occupied': lot.get_occupied_spots_count(),
            'available': lot.get_available_spots_count()
        })
    return jsonify(lots_data)

@app.route('/api/user-stats')
@login_required
def user_stats_api():
    user_id = session.get('user_id')
    completed_reservations = Reservation.query.filter_by(user_id=user_id, status='completed').all()
    
    monthly_data = {}
    for reservation in completed_reservations:
        if reservation.leaving_timestamp:
            month = reservation.leaving_timestamp.strftime('%Y-%m')
            if month not in monthly_data:
                monthly_data[month] = {'count': 0, 'cost': 0}
            monthly_data[month]['count'] += 1
            monthly_data[month]['cost'] += reservation.parking_cost or 0
    
    return jsonify(monthly_data)

@app.route('/admin/search-spots')
@admin_required
def search_spots():
    query = request.args.get('q', '').strip()
    lot_id = request.args.get('lot_id', type=int)
    status = request.args.get('status', '')
    
    spots_query = ParkingSpot.query.join(ParkingLot)
    
    # Apply filters
    if query:
        spots_query = spots_query.filter(
            db.or_(
                ParkingSpot.spot_number.contains(query),
                ParkingLot.prime_location_name.contains(query)
            )
        )
    
    if lot_id:
        spots_query = spots_query.filter(ParkingSpot.lot_id == lot_id)
    
    if status:
        spots_query = spots_query.filter(ParkingSpot.status == status)
    
    spots = spots_query.all()
    return render_template('search_spots.html', spots=spots, query=query, lot_id=lot_id, status=status)

@app.route('/admin/reservations')
@admin_required
def admin_reservations():
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).all()
    return render_template('admin_reservations.html', reservations=reservations)

@app.route('/admin/search-parking-lots')
@admin_required
def search_parking_lots():
    """
    Search and filter parking lots based on user query
    Searches by prime_location_name, address, or pin_code
    """
    query = request.args.get('q', '').strip()
    
    # Get the base query for all parking lots
    lots_query = ParkingLot.query
    
    if query:
        # Search across multiple fields using OR condition
        lots_query = lots_query.filter(
            db.or_(
                ParkingLot.prime_location_name.ilike(f'%{query}%'),
                ParkingLot.address.ilike(f'%{query}%'),
                ParkingLot.pin_code.ilike(f'%{query}%')
            )
        )
    
    # Execute the query and get all matching results
    lots = lots_query.order_by(ParkingLot.prime_location_name).all()
    
    # Render the same template as the main parking lots page
    # but with filtered results and preserving the search query
    return render_template('parking_lots.html', 
                         lots=lots, 
                         search_query=query)