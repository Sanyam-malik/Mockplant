// AJAX wrapper
const fetchData = async (url, options = {}, txt) => {
    try {
        showLoader(txt);
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        hideLoader();
        return await response.json();
    } catch (error) {
        //showError(`Failed to fetch data: ${error.message}`);
        hideLoader();
        throw error;
    }
};
