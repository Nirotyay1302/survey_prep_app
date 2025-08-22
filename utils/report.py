import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
try:
    from weasyprint import HTML  # type: ignore
except Exception:  # pragma: no cover
    HTML = None
from jinja2 import Environment, FileSystemLoader
import base64
from io import BytesIO
import seaborn as sns

def plot_histograms(df, columns):
    """
    Plots histograms for the specified columns in the dataframe.
    Returns a dict: {column_name: base64_png_string}
    """
    images_b64 = {}
    for col in columns:
        plt.figure()
        sns.histplot(df[col].dropna(), kde=True)
        plt.title(f"Histogram of {col}")
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        images_b64[col] = base64.b64encode(buf.read()).decode('utf-8')
    return images_b64

def generate_report_html(summary_df, hist_images, workflow_logs, output_path='report.html', report_title='Survey Data Processing Report', metadata=None):
    env = Environment(loader=FileSystemLoader(searchpath="./templates"))
    template = env.get_template("report_template.html")

    if isinstance(summary_df, pd.DataFrame) and not summary_df.empty:
        summary_html = summary_df.style.format({
            'Weighted Mean': '{:.4f}',
            'Margin of Error (95% CI)': '{:.4f}'
        }).to_html()
    else:
        summary_html = '<em>No summary metrics computed.</em>'

    html_out = template.render(
        title=report_title,
        summary_table=summary_html,
        histograms=hist_images,
        workflow_logs=workflow_logs,
        meta=metadata or {}
    )

    # Save to file for PDF generation
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    # Return both the file path and the raw HTML content
    return output_path, html_out


def generate_pdf_report(html_path, pdf_path='report.pdf'):
    """Generate PDF from HTML if WeasyPrint and system deps are available.
    Returns pdf_path on success, or None on failure.
    """
    try:
        if HTML is None:
            return None
        HTML(html_path).write_pdf(pdf_path)
        return pdf_path
    except Exception:
        return None

def get_pdf_download_link(pdf_path):
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    b64 = base64.b64encode(pdf_data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(pdf_path)}">Download PDF Report</a>'
    return href
