# app/routes/main_routes.py
from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/home")
def home():
    return render_template("dashboard.html")


@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/valet")
def valet():
    return render_template("valet.html")


@main_bp.route("/habilitacao")
def habilitacao():
    return render_template("habilitacao.html")


@main_bp.route("/login")
def login():
    return render_template("login.html")


@main_bp.route("/carteira")
def carteira():
    return render_template("carteira.html")


@main_bp.route("/transferir")
def transferir():
    return render_template("transferir.html")


@main_bp.route("/puxada_master")
def puxada_master():
    return render_template("puxada_master.html")


@main_bp.route("/logs")
def logs_page():
    return render_template("logs.html")


@main_bp.route("/tracking")
def tracking_dashboard():
    return render_template("tracking.html")
