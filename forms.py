from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, ValidationError
from models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please choose a different one.')

class ParkingLotForm(FlaskForm):
    prime_location_name = StringField('Location Name', validators=[DataRequired(), Length(min=3, max=200)])
    price = FloatField('Price per Hour (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
    address = TextAreaField('Address', validators=[DataRequired()])
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(min=6, max=10)])
    maximum_number_of_spots = IntegerField('Maximum Number of Spots', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    submit = SubmitField('Save Parking Lot')
