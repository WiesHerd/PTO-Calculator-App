from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Configure server-side session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
app.config['SESSION_COOKIE_NAME'] = 'my_session'  # Add this line
Session(app)

os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize session data for holidays, vacations, and user inputs
@app.before_request
def before_request():
    if 'holidays' not in session:
        session['holidays'] = []
    if 'vacations' not in session:
        session['vacations'] = []
    if 'holiday_list' not in session:
        session['holiday_list'] = ['New Year\'s Day', 'Independence Day', 'Thanksgiving', 'Christmas Day']
    if 'user_inputs' not in session:
        session['user_inputs'] = {
            'start_date': '',
            'current_pto': '',
            'current_pp_start': '',
            'future_date': '',
            'include_holidays': True
        }
    if 'accrual_rates' not in session:
        session['accrual_rates'] = [{'years': 0, 'hours': 8}]  # Default accrual rates if none are provided.

# Apply accrual rates based on years of service
def get_accrual_rate(years_of_service):
    accrual_rates = session.get('accrual_rates', [])
    accrual_rate = 8  # Default accrual rate
    for rate in accrual_rates:
        if years_of_service >= rate['years']:
            accrual_rate = rate['hours']
    return accrual_rate

@app.route("/", methods=["GET", "POST"])
def home():
    holidays = session.get('holidays', [])
    vacations = session.get('vacations', [])
    user_inputs = session.get('user_inputs', {})
    total_holiday_hours = sum(float(holiday['hours']) for holiday in holidays)
    total_vacation_hours = sum(float(vacation['hours']) for vacation in vacations)

    if request.method == "POST":
        # Fetch input data
        start_date_str = request.form.get('start_date')
        current_pto_str = request.form.get('current_pto')
        current_pp_start_str = request.form.get('current_pp_start')
        future_date_str = request.form.get('future_date')
        include_holidays = request.form.get('include_holidays') == 'on'

        # Store inputs in session
        session['user_inputs']['start_date'] = start_date_str
        session['user_inputs']['current_pto'] = current_pto_str
        session['user_inputs']['current_pp_start'] = current_pp_start_str
        session['user_inputs']['future_date'] = future_date_str
        session['user_inputs']['include_holidays'] = include_holidays
        session.modified = True

        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            future_date = datetime.strptime(future_date_str, "%Y-%m-%d")
            current_pp_start = datetime.strptime(current_pp_start_str, "%Y-%m-%d")
            current_pto = float(current_pto_str)
        except ValueError:
            return render_template("index.html", error_message="Invalid date or PTO input.", user_inputs=user_inputs)

        pto_detail = []
        total_pto_hours = current_pto

        # Create pay periods from current pay period start date to future date
        pay_periods = []
        period_start = current_pp_start
        while period_start <= future_date:
            period_end = period_start + timedelta(days=13)
            pay_periods.append({'start': period_start, 'end': period_end})
            period_start += timedelta(days=14)

        vacation_hours_deducted = set()

        pay_periods_with_time_off = []
        for period in pay_periods:
            period_vacation_hours = 0
            period_holiday_hours = 0
            vacation_dates = []
            holiday_dates = []

            # Track vacations deducted to avoid double counting
            for vacation in vacations:
                vacation_key = f"{vacation['start']} to {vacation['end']}"
                vacation_start = datetime.strptime(vacation['start'], "%Y-%m-%d")
                vacation_end = datetime.strptime(vacation['end'], "%Y-%m-%d")
                if vacation_key not in vacation_hours_deducted and period['start'] <= vacation_end and period['end'] >= vacation_start:
                    period_vacation_hours += float(vacation['hours'])
                    vacation_dates.append(f"{vacation['start']} to {vacation['end']}")
                    vacation_hours_deducted.add(vacation_key)

            # Check for holidays
            if include_holidays:
                for holiday in holidays:
                    holiday_date = datetime.strptime(holiday['date'], "%Y-%m-%d")
                    if period['start'] <= holiday_date <= period['end']:
                        period_holiday_hours += float(holiday['hours'])
                        holiday_dates.append(holiday['date'])

            pay_periods_with_time_off.append({
                'start': period['start'],
                'end': period['end'],
                'vacation_hours': period_vacation_hours,
                'holiday_hours': period_holiday_hours,
                'vacation_dates': vacation_dates,
                'holiday_dates': holiday_dates
            })

        # Recalculate PTO using the correct accrual rate based on tenure
        for period in pay_periods_with_time_off:
            period_tenure_days = (period['end'] - start_date).days
            period_tenure_years = max(0, period_tenure_days / 365.25)

            # Get dynamic accrual rate based on service years
            accrual_rate = get_accrual_rate(period_tenure_years)
            hours_accrued = accrual_rate

            total_pto_hours += hours_accrued
            total_pto_hours -= period['vacation_hours']
            total_pto_hours -= period['holiday_hours']

            pto_detail.append({
                "pay_period_start": period['start'].strftime("%Y-%m-%d"),
                "pay_period_end": period['end'].strftime("%Y-%m-%d"),
                "length_of_service": round(period_tenure_years, 2),
                "hours_accrued": round(hours_accrued, 2),
                "vacation_hours": round(period['vacation_hours'], 2),
                "holiday_hours": round(period['holiday_hours'], 2),
                "total_pto_hours": round(total_pto_hours, 2),
                "total_pto_days": round(total_pto_hours / 8, 2),
                "vacation_dates": ", ".join(period['vacation_dates']),
                "holiday_dates": ", ".join(period['holiday_dates'])
            })

        forecasted_pto = total_pto_hours

        return render_template(
            "index.html",
            holidays=holidays,
            vacations=vacations,
            forecasted_pto=round(forecasted_pto, 2),
            future_date=future_date_str,
            pto_detail=pto_detail,
            user_inputs=session['user_inputs'],
            total_holiday_hours=total_holiday_hours,
            total_vacation_hours=total_vacation_hours
        )
    else:
        forecasted_pto = None
        pto_detail = []

        return render_template(
            "index.html",
            holidays=holidays,
            vacations=vacations,
            forecasted_pto=forecasted_pto,
            pto_detail=pto_detail,
            user_inputs=user_inputs,
            total_holiday_hours=total_holiday_hours,
            total_vacation_hours=total_vacation_hours
        )

@app.route("/vacations", methods=["GET", "POST"])
def vacations_view():
    holidays = session.get('holidays', [])
    vacations = session.get('vacations', [])
    holiday_list = session.get('holiday_list', ['New Year\'s Day', 'Memorial Day', 'Independence Day', 'Labor Day', 'Thanksgiving', 'Christmas'])
    
    if request.method == "POST":
        new_holidays = []
        new_vacations = []
        
        # Process holidays
        holiday_dates = request.form.getlist('holidays[]')
        holiday_hours = request.form.getlist('holiday_hours[]')
        holiday_names = request.form.getlist('holiday_names[]')
        custom_holiday_names = request.form.getlist('custom_holiday_names[]')
        
        for i in range(len(holiday_dates)):
            name = holiday_names[i] if holiday_names[i] != 'custom' else custom_holiday_names[i]
            new_holidays.append({
                'date': holiday_dates[i],
                'hours': float(holiday_hours[i]),
                'name': name
            })
        
        # Process vacations
        vacation_starts = request.form.getlist('vacation_start[]')
        vacation_ends = request.form.getlist('vacation_end[]')
        vacation_hours = request.form.getlist('vacation_hours[]')
        
        for i in range(len(vacation_starts)):
            new_vacations.append({
                'start': vacation_starts[i],
                'end': vacation_ends[i],
                'hours': float(vacation_hours[i])
            })
        
        session['holidays'] = new_holidays
        session['vacations'] = new_vacations
        session.modified = True
        
        return redirect(url_for('home'))

    return render_template('vacations.html', holidays=holidays, vacations=vacations, holiday_list=holiday_list)

@app.route("/accruals", methods=["GET", "POST"])
def accruals_view():
    accrual_rates = session.get('accrual_rates', [])
    
    if request.method == "POST":
        new_accrual_rates = []
        years = request.form.getlist('years[]')
        hours = request.form.getlist('hours[]')
        
        for i in range(len(years)):
            new_accrual_rates.append({
                'years': int(years[i]),
                'hours': float(hours[i])
            })
        
        session['accrual_rates'] = new_accrual_rates
        session.modified = True
        
        return redirect(url_for('home'))

    return render_template('accruals.html', accrual_rates=accrual_rates)

if __name__ == "__main__":
    app.run(debug=True)