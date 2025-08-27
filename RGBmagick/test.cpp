#include <iostream>
#include <format>
#include <vector>
#include <filesystem>

#include <Magick++.h>
//#include <magick/MagickCore.h>


extern "C" { // libRGBmagick.so exports //
void PythonPlz(const wchar_t ezString[]) { // easy for python, that is. python strings are UTF8 (wchar_t)
	std::cout << "\r"; // something must be written to std::cout before ever using std::wcout; otherwise,
	// output will never appear on std::cout!! (affects everything; executable and shared-library/FFI.py)
	std::wcout << L"  [PythonPlz]: " << ezString << std::endl;
}

int EpicFunction(int argc, const char* argv[]) {
	for (int C{0}; C < argc; C++) {
		std::cout << "  [EpicFunction]: ";
		std::cout << C << ": " << argv[C] << '\n';
	}
	return 69;
}

const char* GetImageSize(const char imagepath[]) {
	static std::string _ImageSizeString{"[0x0]"};
	try { Magick::Image testimage(imagepath); testimage.verbose(true);
		_ImageSizeString = std::format("[{}x{}]", testimage.columns(), testimage.rows());
	} catch (Magick::ErrorBlob& error){ _ImageSizeString = std::format("[ERROR] {}", error.what());}
	return _ImageSizeString.c_str();
}

}// extern "C"

// TODO: prevent ImageMagick from writing temp/cache files to the current directory!!!

// Magick::readImages doesn't accept format-specifiers ("frame%03d.png"); it must be loaded manually
std::vector<Magick::Image> LoadImageDirectory(std::string directory) {
	std::vector<Magick::Image> imageList{}; imageList.reserve(1000);
	// this iterates the files in REVERSE order
	for(std::filesystem::directory_entry const& file: 
		std::filesystem::directory_iterator{directory}) {
		imageList.push_back(Magick::Image(file.path()));
	}
	std::cout << std::format("{} loaded: {} images", directory, imageList.size()) << '\n';
	return imageList;
}

Magick::Image ImageGrid(int stack_count, std::vector<Magick::Image>& imageList) {
	std::vector<Magick::Image> stacks{}; stacks.reserve(10);
	try {
		for(auto iter {imageList.rbegin()}; iter < imageList.rend();) {
			std::cout << "next stack: " << iter->fileName() << '\n';
			Magick::Image& stacked{stacks.emplace_back()};
			Magick::appendImages(&stacked, iter, iter+stack_count, true); // vertical
			iter += stack_count;
		}
	} catch (Magick::Exception &error) { std::cout << "error: " << error.what() << '\n'; }
	
	Magick::Image framegrid{};
	Magick::appendImages(&framegrid, stacks.begin(), stacks.end(), false); // horizontal
	std::cout << std::format("stacks: {}x{}", stacks.size(), stack_count) << '\n';
	std::cout << "final size: " << std::format("[{}x{}]", framegrid.columns(), framegrid.rows()) << '\n';
	return framegrid;
}


// stripped from library //
#ifndef IS_LIBRARY_BUILD
void PrintBuildInfo() {
	std::cout << "RGBmagick!!!";
	#ifdef MAGICKCORE_QUANTUM_DEPTH
	std::cout << " [QUANTUM_DEPTH: " << MAGICKCORE_QUANTUM_DEPTH << ']';
	#endif
	std::cout << '\n';
	
	#if MAGICKCORE_HDRI_ENABLE
	std::cout << "HDRI support enabled!!!\n";
	#endif
	
	#ifdef MAGICKCORE_MODULES_RELATIVE_PATH
	// I think this and a few other variables in "magick-config.h" should be defined...
	std::cout << "MAGICKCORE_MODULES_RELATIVE_PATH: " << MAGICKCORE_MODULES_RELATIVE_PATH << '\n';
	#endif
}

int main(int argc, const char* argv[])
{
	PrintBuildInfo();
	std::cout << "argc: " << argc << '\n';
	for (int C{0}; C < argc; C++) {
		std::cout << C << ": ";
		std::cout << argv[C] << '\n';
	}
	
	std::cout << '\n';
	PythonPlz(L"Plz Print This WideString Plz C++");
	EpicFunction(argc, argv);
	std::cout << '\n';
	
	std::cout << "testimages/peach.png\n";
	Magick::Image testimage("testimages/peach.png");
	std::cout << testimage.magick() << '\n'; // PNG
	std::cout << GetImageSize("testimages/peach.png") << '\n';
	std::cout << '[' << testimage.columns() << 'x' << testimage.rows() << "]\n";
	std::cout << std::endl;
	
	std::vector<Magick::Image> imageList = LoadImageDirectory("/tmp/RGB_TOPLEVEL/frames/");
	Magick::Image framegrid = ImageGrid(10, imageList);
	framegrid.write("/tmp/RGB_TOPLEVEL/output/frame_grid.png");
	return 0;
}

#endif //NOT_LIBRARY_BUILD
