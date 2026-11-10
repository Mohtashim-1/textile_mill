frappe.pages["dm-stage"].on_page_load = function (wrapper) {
	frappe.require(["dm_dashboard.bundle.js", "dm_dashboard.bundle.css"], () => textile_mill.mount_dashboard(wrapper, "stage"));
};

frappe.pages["dm-stage"].on_page_show = function (wrapper) {
	wrapper.dm_dashboard?.on_show();
};
