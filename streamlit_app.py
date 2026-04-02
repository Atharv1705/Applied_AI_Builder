import streamlit as st
import tempfile
from pathlib import Path

st.set_page_config(page_title="DDR Report Generator", page_icon="🏗️")
st.title("🏗️ Detailed Diagnostic Report Generator")
st.markdown("Upload an **Inspection PDF** and a **Thermal PDF** to generate a DDR report.")

ins_file = st.file_uploader("Inspection Report (PDF)", type="pdf")
th_file  = st.file_uploader("Thermal Report (PDF)", type="pdf")

if ins_file and th_file:
    if st.button("Generate DDR Report", type="primary"):
        with st.spinner("Processing PDFs and generating report... this may take a minute."):
            try:
                from ddr_builder.pipeline import run_pipeline
                from ddr_builder.report_generator import build_ddr_pdf, build_ddr_docx

                with tempfile.TemporaryDirectory() as tmp:
                    tmp = Path(tmp)
                    ins_path = tmp / "inspection.pdf"
                    th_path  = tmp / "thermal.pdf"
                    ins_path.write_bytes(ins_file.read())
                    th_path.write_bytes(th_file.read())

                    out_dir = tmp / "output"
                    result = run_pipeline(ins_path, th_path, out_dir)

                    pdf_path  = out_dir / "DDR_Report.pdf"
                    docx_path = out_dir / "DDR_Report.docx"
                    build_ddr_pdf(result.ddr, pdf_path, base_dir=out_dir)
                    build_ddr_docx(result.ddr, docx_path, base_dir=out_dir)

                    pdf_bytes  = pdf_path.read_bytes()
                    docx_bytes = docx_path.read_bytes()

                st.success("Report generated successfully!")

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "📄 Download PDF",
                        pdf_bytes,
                        file_name="DDR_Report.pdf",
                        mime="application/pdf",
                    )
                with col2:
                    st.download_button(
                        "📝 Download Word (.docx)",
                        docx_bytes,
                        file_name="DDR_Report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )

                st.divider()

                # Property Summary
                st.subheader("📋 Property Summary")
                st.info(result.ddr.property_summary or "Not Available")

                # Severity bands
                col_h, col_m, col_l = st.columns(3)
                with col_h:
                    st.metric("🔴 High Severity", len(result.ddr.high_severity))
                with col_m:
                    st.metric("🟡 Medium Severity", len(result.ddr.medium_severity))
                with col_l:
                    st.metric("🟢 Low Severity", len(result.ddr.low_severity))

                # Area-wise preview
                if result.ddr.areas:
                    st.subheader("🏠 Area-wise Findings")
                    for area in result.ddr.areas:
                        with st.expander(f"📍 {area.area_name}", expanded=False):
                            st.markdown(f"**Observation:** {area.observation or 'Not Available'}")
                            st.markdown(f"**Thermal Finding:** {area.thermal_finding or 'Not Available'}")
                            st.markdown(f"**Root Cause:** {area.root_cause or 'Not Available'}")
                            sev_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(area.severity, "⚪")
                            st.markdown(f"**Severity:** {sev_color} {area.severity or 'Not Available'} — {area.severity_reason or ''}")
                            st.markdown(f"**Recommended Action:** {area.recommended_action or 'Not Available'}")
                            if area.conflict_note:
                                st.warning(f"⚠️ Conflict: {area.conflict_note}")

                # Conflicts
                if result.ddr.conflicts:
                    st.subheader("⚠️ Conflicts Detected")
                    for c in result.ddr.conflicts:
                        st.warning(c)

                # Missing information
                if result.ddr.missing_information:
                    st.subheader("ℹ️ Missing Information")
                    thermal_notes = [m for m in result.ddr.missing_information if "thermal" in m.lower()]
                    other_notes   = [m for m in result.ddr.missing_information if "thermal" not in m.lower()]
                    if other_notes:
                        with st.expander(f"Inspection gaps ({len(other_notes)} items)", expanded=False):
                            for m in other_notes:
                                st.caption(f"• {m}")
                    if thermal_notes:
                        with st.expander(f"Thermal mapping notes ({len(thermal_notes)} items)", expanded=False):
                            for m in thermal_notes:
                                st.caption(f"• {m}")

                # Intermediate JSON — shows pipeline reasoning layer
                st.subheader("🔍 Intermediate Reasoning JSON")
                st.caption("This structured layer is generated before the final report — it shows how the system reasons about root causes, severity, and conflicts.")
                with st.expander("View intermediate JSON", expanded=False):
                    import json
                    st.json(json.loads(result.ddr.model_dump_json()))

            except Exception as e:
                st.error(f"Error generating report: {e}")
else:
    st.info("Please upload both PDFs to continue.")
