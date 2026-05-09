#!/bin/bash

check_and_install_unzip() {
    if command -v unzip &> /dev/null; then
        echo "unzip cmd is already installed."
        return 0
    fi

    echo "unzip cmd is not installed. Attempting to install..."

    if [ -x "$(command -v apt)" ]; then
        sudo apt update && sudo apt install -y unzip
    elif [ -x "$(command -v yum)" ]; then
        sudo yum install -y unzip
    elif [ -x "$(command -v dnf)" ]; then
        sudo dnf install -y unzip
    else
        echo "Unsupported package manager. Please install unzip manually."
        return 1
    fi

    # Verify if installation succeeded
    if command -v unzip &> /dev/null; then
        echo "unzip cmd successfully installed."
        return 0
    else
        echo "Failed to install unzip cmd."
        return 1
    fi
}

main() {
    if check_and_install_unzip; then
        echo "Unzip cmd is ready to use."
    else
        echo "Unzip cmd could not be installed. Exiting..."
        exit 1
    fi
}

# Call the main function
main
